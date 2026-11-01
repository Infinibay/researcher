/** Verify saved-report title preservation, explicit UTC dates and scoped URL IDs. @module */

import assert from 'node:assert/strict'
import { test } from 'node:test'
import { reportDocument,reportTimestamp } from '../src/components/reports/presentation.ts'
import { scopedEntityId } from '../src/utils/projectSelection.ts'
test('URL selection requires matching project and a positive safe integer',()=>{
 for(const [query,expected] of [['project=101&task=24',24],['project=202&task=24',null],['project=101&task=24junk',null],['project=101&task=-2',null],['project=101&task=1.5',null],['task=24',null]] as const)
  assert.equal(scopedEntityId(new URLSearchParams(query),101,'task'),expected)
 assert.equal(scopedEntityId(new URLSearchParams('project=101&artifact=9'),101,'artifact'),9)
})
test('reading omits only an exact duplicate title and preserves the remaining Markdown',()=>{
 assert.equal(reportDocument('# Informe\n\nTexto original','Informe'),'\nTexto original')
 assert.equal(reportDocument('# Otro título\n\nTexto original','Informe'),'# Otro título\n\nTexto original')
})
test('SQLite timestamps are interpreted as UTC and unknown dates remain unknown',()=>{
 assert.equal(reportTimestamp('2026-11-01 17:39:00').machine,'2026-11-01T17:39:00.000Z')
 assert.equal(reportTimestamp('2026-11-01T14:39:00-03:00').machine,'2026-11-01T17:39:00.000Z')
 assert.match(reportTimestamp('2026-11-01 17:39:00').label,/UTC/)
 assert.equal(reportTimestamp('unknown').machine,undefined)
 assert.equal(reportTimestamp(undefined).machine,undefined)
})
