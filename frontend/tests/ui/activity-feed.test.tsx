/** Make missing history and temporary disconnects visible without claiming execution completion. @module */
import {render,screen,act} from '@testing-library/react'
import {expect,it} from 'vitest'
import {ActivityFeed} from '../../src/components/chat/ActivityFeed'
import {useActivityFeedStore} from '../../src/stores/activityFeed'

it('keeps the last observation while reconnecting and preserves a gap warning after recovery',()=>{
 const store=useActivityFeedStore.getState(),generation=store.selectProject(101)
 store.addEvent(101,generation,{id:'1',type:'run.observed',timestamp:'',content:'Resultado guardado'})
 store.setConnection(101,generation,'reconnecting')
 render(<ActivityFeed/>)
 expect(screen.getByRole('status')).toHaveTextContent('Reconectando')
 expect(screen.getByText('Resultado guardado')).toBeVisible()
 expect(screen.getByText('Fecha no registrada')).toBeVisible()
 act(()=>store.setConnection(101,generation,'reset_required'))
 expect(screen.getByRole('alert')).toHaveTextContent('Una parte del historial ya no está disponible')
 expect(screen.queryByText('Resultado guardado')).toBeNull()
 act(()=>store.setConnection(101,generation,'live'))
 expect(screen.getByRole('status')).toHaveTextContent('Historial al día')
 expect(screen.getByRole('alert')).toBeVisible()
})
