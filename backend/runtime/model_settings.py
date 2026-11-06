"""Owner model/effort inheritance and immutable attempt selection, distinct from subscription credentials, permissions and actual inference provenance."""

import json
import re
import time

from backend.runtime.contracts import RunConflict,RunNotFound,identity,text


class ModelUnavailable(RunConflict):
    """The original requested model/effort is absent from the current native catalog; no substitute or billed provider may be dispatched."""


def model_profile(model,reasoning_effort):
    """Validate a complete model/effort pair without guessing account eligibility or interpreting identifiers as executable arguments."""
    if not isinstance(model,str) or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9._:/-]{0,127}',model):
        raise ValueError('El identificador del modelo no es válido.')
    if not isinstance(reasoning_effort,str) or not re.fullmatch(r'[a-z][a-z0-9_]{0,31}',reasoning_effort):
        raise ValueError('Indica el esfuerzo de razonamiento de Codex.')
    return {'model':model,'reasoning_effort':reasoning_effort}


class ModelSettings:
    """Persist explicit global/project/project-actor overrides; resolve a whole pair and freeze it once for each actually owned attempt."""

    def __init__(self,runs):
        """Reuse the serving run store and its transactions without starting native processes or modifying host configuration."""
        self.runs=runs

    @staticmethod
    def _scope(conn,project_id=None,actor_id=None):
        """Validate the requested scope, including project existence; actor overrides are always local to one explicit project."""
        if project_id is None:
            if actor_id is not None:raise ValueError('Elige el proyecto del agente antes de cambiar su modelo.')
            return 'global'
        identity(project_id)
        if not conn.execute('SELECT 1 FROM projects WHERE id=?',(project_id,)).fetchone():raise RunNotFound('Project not found')
        if actor_id is None:return 'project:'+str(project_id)
        text(actor_id,'actor_id',128)
        return 'actor:'+str(project_id)+':'+actor_id

    @staticmethod
    def _setting(conn,key):
        """Retain reset revisions as tombstones so an old editor cannot overwrite a newer inheritance decision."""
        row=conn.execute('SELECT revision,profile_json FROM runtime_model_settings WHERE scope_key=?',(key,)).fetchone()
        return {'scope':key,'revision':row['revision'] if row else 0,'profile':json.loads(row['profile_json']) if row and row['profile_json'] is not None else None}

    def _resolve(self,conn,project_id,actor_id,host_model,host_effort):
        """Select the most specific complete override, falling through explicit inheritance to the observed host default."""
        key=self._scope(conn,project_id,actor_id)
        keys=[key]
        if actor_id is not None:keys.append('project:'+str(project_id))
        if key!='global':keys.append('global')
        for candidate in keys:
            setting=self._setting(conn,candidate)
            if setting['profile'] is not None:
                return {**model_profile(**setting['profile']),'source':candidate,'revision':setting['revision']}
        return {**model_profile(host_model,host_effort),'source':'host','revision':0}

    def view(self,project_id=None,actor_id=None,*,host_model,host_effort='low'):
        """Expose editable local policy and resolved future-attempt choice, without claiming the subscription currently permits that model."""
        with self.runs._transaction() as conn:
            key=self._scope(conn,project_id,actor_id)
            return {'project_id':project_id,'actor_id':actor_id,'setting':self._setting(conn,key),'effective':self._resolve(conn,project_id,actor_id,host_model,host_effort)}

    def update(self,*,expected_revision,model,reasoning_effort,project_id=None,actor_id=None):
        """Compare and replace one owner setting or reset it to inheritance; changed settings never rewrite already selected attempts."""
        if type(expected_revision) is not int or expected_revision<0:raise ValueError('Invalid model setting revision')
        if (model is None)!=(reasoning_effort is None):raise ValueError('Restablece ambos campos o selecciona modelo y esfuerzo juntos.')
        profile=model_profile(model,reasoning_effort) if model is not None else None
        with self.runs._transaction(write=True) as conn:
            key=self._scope(conn,project_id,actor_id);current=self._setting(conn,key)
            if current['revision']!=expected_revision:raise RunConflict('La configuración cambió. Consulta la versión actual antes de guardar; conservamos tu selección.')
            conn.execute('INSERT INTO runtime_model_settings(scope_key,project_id,actor_id,revision,profile_json,updated_at) VALUES(?,?,?,?,?,?) ON CONFLICT(scope_key) DO UPDATE SET revision=excluded.revision,profile_json=excluded.profile_json,updated_at=excluded.updated_at',
                         (key,project_id,actor_id,expected_revision+1,json.dumps(profile) if profile is not None else None,self.runs.clock()))
            return self._setting(conn,key)

    def freeze(self,lease,*,host_model,host_effort='low'):
        """Persist original model/effort/source/revision under the actual current attempt lease before any native dispatch; repeated reads cannot reselect it."""
        with self.runs._transaction(write=True) as conn:
            self.runs._authority(conn,lease)
            previous=conn.execute('SELECT selection_json FROM runtime_attempt_models WHERE attempt_id=?',(lease.attempt_id,)).fetchone()
            if previous:return json.loads(previous['selection_json'])
            selected={**self._resolve(conn,lease.project_id,lease.actor_id,host_model,host_effort),'project_id':lease.project_id,'actor_id':lease.actor_id,'run_id':lease.run_id,'attempt_id':lease.attempt_id,'fence':lease.fence,'selected_at':self.runs.clock()}
            conn.execute('INSERT INTO runtime_attempt_models(attempt_id,selection_json) VALUES(?,?)',(lease.attempt_id,json.dumps(selected)))
            self.runs._event(conn,lease.project_id,lease.task_id,'run.model_selected',selected)
            return selected


async def validate_native_model(rpc,selected,cache):
    """Read bounded actual account catalog pages before thread/turn creation, cache only public observations, and reject unavailable model/effort without substitution."""
    models=[];cursor=None;seen=set()
    for _ in range(8):
        params={'limit':100,'includeHidden':False}
        if cursor is not None:params['cursor']=cursor
        page=await rpc.request('model/list',params)
        data=page.get('data')
        if not isinstance(data,list) or len(data)>100:raise ModelUnavailable('No se pudo verificar el catálogo de modelos de la suscripción.')
        for item in data:
            if not isinstance(item,dict):raise ModelUnavailable('Catálogo de modelos incompleto.')
            model=item.get('model');efforts=item.get('supportedReasoningEfforts');label=item.get('displayName',model)
            if not isinstance(model,str) or not isinstance(efforts,list) or not isinstance(label,str) or len(label)>256:raise ModelUnavailable('Catálogo de modelos incompleto.')
            values=[]
            for effort in efforts:
                value=effort.get('reasoningEffort') if isinstance(effort,dict) else None
                try:model_profile(model,value)
                except ValueError as error:raise ModelUnavailable('El catálogo no identifica sus esfuerzos disponibles.') from error
                values.append(value)
            if model in seen:raise ModelUnavailable('El catálogo repitió un identificador; no se eligió otro modelo.')
            seen.add(model);models.append({'model':model,'label':label,'reasoning_efforts':values})
        following=page.get('nextCursor')
        if following is None:break
        if not isinstance(following,str) or not following or following==cursor:raise ModelUnavailable('No se pudo completar la consulta del catálogo.')
        cursor=following
    else:raise ModelUnavailable('El catálogo excedió el límite de consulta; no se envió un turno.')
    cache.clear();cache.update(models=models,observed_at=time.time(),kind='observed_not_rechecked')
    if not any(item['model']==selected['model'] and selected['reasoning_effort'] in item['reasoning_efforts'] for item in models):
        raise ModelUnavailable('El modelo o esfuerzo elegido no está disponible en este catálogo de Codex. Revisa la configuración; no se utilizó otro modelo.')
