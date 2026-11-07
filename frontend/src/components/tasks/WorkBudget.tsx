/** Explain recorded project capacity without implying knowledge of subscription billing. @module */
import {useQuery} from '@tanstack/react-query'
import {measuredTokens,workBudget} from '../../api/history'
import {BudgetPolicyEditor} from './BudgetPolicyEditor'

/** Observe lifetime admission limits, held capacity and partial measurements in the actual project. */
export function WorkBudget({projectId}:{projectId:number}){
 const query=useQuery({queryKey:['work-budget',projectId],queryFn:()=>workBudget(projectId),retry:false,refetchInterval:10000})
 const budget=query.data?.project_id===projectId?query.data:undefined
 return <section className="space-y-2 border-b border-[var(--work-line)] p-5" aria-label="Presupuesto de trabajo del proyecto">
  <h2 className="font-semibold">Presupuesto de trabajo</h2>
  <p>Este límite del proyecto cuenta solicitudes reservadas y tokens contabilizados para admitir trabajo. Cuota y coste de la suscripción: no disponibles.</p>
  {query.isPending&&<p role="status">Consultando el presupuesto…</p>}
  {query.error&&<div role="alert"><p>No se pudo consultar el presupuesto.{budget?' Se conserva la última consulta correcta.':''}</p><button className="min-h-11 underline" onClick={()=>query.refetch()}>Volver a consultar presupuesto</button></div>}
  {budget&&<>
   {!budget.policy?<p>Todavía no se registró un límite de trabajo para este proyecto.</p>:<>
    <dl className="grid gap-3 sm:grid-cols-3">
     <div><dt>Solicitudes reservadas</dt><dd>{budget.used_turns} de {budget.policy.turn_limit}</dd></div>
     <div><dt>Tokens contabilizados para el límite</dt><dd>{measuredTokens(budget.accounted_tokens)} de {measuredTokens(budget.policy.token_limit)}</dd></div>
     <div><dt>Capacidad restante en tokens</dt><dd>{measuredTokens(budget.remaining_tokens)}</dd></div>
    </dl>
    <p>Se mantienen reservados {measuredTokens(budget.held_tokens)} tokens por recibos pendientes o sin medición. Ya están incluidos en lo contabilizado.</p>
    {budget.overrun_tokens!=null&&budget.overrun_tokens>0&&<p role="status">Las observaciones superan el límite en {measuredTokens(budget.overrun_tokens)} tokens. La capacidad restante es cero; el registro conserva el exceso.</p>}
   </>}
   <dl><dt>Tokens observados en los recibos disponibles</dt><dd>{measuredTokens(budget.observed_tokens)}</dd></dl>
   <p>{budget.unmeasured_dispatches} solicitudes sin medición y {budget.unsettled_dispatches} sin recibo final. Las observaciones pueden ser parciales, incluso en un recibo cerrado.</p>
   <details><summary className="min-h-11 cursor-pointer">Cómo interpretar la reserva</summary><p>Por ejemplo: con una reserva de 100 tokens y 40 observados durante el trabajo, se mantienen contabilizados 100. Si el consumo queda desconocido, la reserva se conserva. Este registro acumula la historia del proyecto; no se reinicia al cambiar de página.</p></details>
   {budget.auxiliary&&<div className="space-y-2 border-t border-[var(--work-line)] pt-3" aria-label="Procesamiento local">
    <h3 className="font-semibold">Documentos y búsqueda local</h3>
    <p>Usuario y agentes comparten este cupo del proyecto. No son tokens ni cargos de la suscripción.</p>
    <dl className="grid gap-3 sm:grid-cols-2"><div><dt>Cálculos reservados</dt><dd>{budget.auxiliary.used_operations} de {budget.auxiliary.policy.operation_limit}</dd></div><div><dt>CPU contabilizada (ms)</dt><dd>{measuredTokens(budget.auxiliary.accounted_cpu_ms)} de {measuredTokens(budget.auxiliary.policy.cpu_ms_limit)}</dd></div><div><dt>CPU observada (ms)</dt><dd>{measuredTokens(budget.auxiliary.observed_cpu_ms)}</dd></div><div><dt>Capacidad local restante (ms)</dt><dd>{measuredTokens(budget.auxiliary.remaining_cpu_ms)}</dd></div></dl>
    <p>{budget.auxiliary.unknown_operations} cálculos sin medición; conservan {measuredTokens(budget.auxiliary.held_cpu_ms)} ms reservados, ya incluidos en el total. {budget.auxiliary.pending_operations} sin recibo final.</p>
    <p>Por ejemplo: si se reservan 3.000 ms para extraer un documento y se pierde la medición, esos 3.000 ms siguen contabilizados. Un resultado completo guardado puede recuperarse sin recalcular. Ampliar el cupo no repite cálculos inciertos.</p>
   </div>}
   <BudgetPolicyEditor key={projectId} budget={budget} fresh={!query.error}/>
  </>}
 </section>
}
