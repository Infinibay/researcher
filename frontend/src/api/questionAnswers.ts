/** Durable original question answers, scoped to their real run and recoverable after the question becomes historical. @module */
import {ownerActionStore,type OwnerActionStorage} from './ownerActions.ts'
import {prepareAnswer,restoreAnswer,type AnswerIntent,type RuntimeQuestion,type QuestionAnswer} from './runtime.ts'

/** The real question run identifies the stored packet; no fictitious execution identity is introduced. */
export type AnswerPacket=Readonly<AnswerIntent&{schema:1;kind:'answer';runId:string}>

/** Reject damaged or ambiguous storage while preserving original option identities and literal typed text. */
function parse(value:unknown):AnswerPacket{
 const p=value as AnswerPacket
 if(!p||p.schema!==1||p.kind!=='answer'||typeof p.runId!=='string'||!p.runId||p.runId.length>128||Object.keys(p).sort().join(',')!=='body,kind,projectId,questionId,runId,schema,taskId'||!p.body||Object.keys(p.body).sort().join(',')!=='answers,expected_version,operation_key')throw new Error('Original answer identity is invalid')
 const original=restoreAnswer(p)
 return Object.freeze({...p,body:original.body})
}
const records=ownerActionStore<AnswerPacket>('question-answer',parse)

/** Capture the observed question context before saving and sending any answer. */
export function prepareAnswerPacket(projectId:number,taskId:number,question:RuntimeQuestion,answers:Record<string,QuestionAnswer>):AnswerPacket{
 return parse({...prepareAnswer(projectId,taskId,question.request_id,question.context_version,answers),schema:1,kind:'answer',runId:question.run_id})
}
/** Restore only this original question; another question from the run cannot silently acquire its response. */
export function loadAnswerPacket(storage:Pick<Storage,'getItem'>,projectId:number,taskId:number,question:RuntimeQuestion){
 const packet=records.load(storage,projectId,taskId,question.run_id)
 if(packet&&packet.questionId!==question.request_id)throw new Error('La respuesta guardada pertenece a otra pregunta. Consulta el historial antes de continuar.')
 return packet
}
/** Save before transport; existing shared pointers also prevent replacing another unresolved task answer. */
export function saveAnswerPacket(storage:OwnerActionStorage,packet:AnswerPacket){records.save(storage,parse(packet))}
/** Retire only the exact original copy; a later intent remains intact. */
export const clearAnswerPacket=records.clear

/** The endpoint confirms the original expected context once and never starts inference when answering. */
export function verifyAnswerReceipt(packet:AnswerPacket,result:{context_version:number;application:string;inference_started:boolean}){
 if(result.context_version!==packet.body.expected_version+1||result.application!=='recorded_for_next_run'||result.inference_started!==false)throw new Error('El recibo no confirma estas respuestas originales; se conserva la copia.')
}
