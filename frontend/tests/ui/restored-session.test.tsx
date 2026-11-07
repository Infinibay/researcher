/** Verify the owner's correction step preserves unsent intent when the server database changes. @module */
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { QueryClient, QueryClientProvider } from '@tanstack/react-query'
import { expect, it, vi } from 'vitest'
import { OwnerSessionGate } from '../../src/components/session/OwnerSessionGate'
import { invalidateOwnerSession } from '../../src/api/session'
import { useWikiDrafts } from '../../src/stores/wikiDrafts'

it('explains a changed installation, keeps content locked and archives pending packets before explicit entry', async () => {
  sessionStorage.clear()
  invalidateOwnerSession()
  sessionStorage.setItem('researcher:owner-endpoint:v1','old-database')
  sessionStorage.setItem('researcher:source-setup:v1:101','exact unsent owner intent')
  const before = useWikiDrafts.getState().drafts
  const fetch = vi.spyOn(globalThis,'fetch').mockResolvedValue(Response.json({authenticated:true,csrf_token:'fixture',endpoint_id:'restored-database'}))
  try {
    const user = userEvent.setup()
    render(<QueryClientProvider client={new QueryClient()}><OwnerSessionGate><h1>Contenido privado</h1></OwnerSessionGate></QueryClientProvider>)
    expect(await screen.findByRole('heading',{name:'Esta instalación cambió'})).toBeVisible()
    expect(screen.queryByRole('heading',{name:'Contenido privado'})).toBeNull()
    expect(screen.getByText(/publicación pendiente/)).toBeVisible()
    expect(sessionStorage.getItem('researcher:source-setup:v1:101')).toBe('exact unsent owner intent')
    await user.click(screen.getByRole('button',{name:'Archivar anteriores y abrir esta instalación'}))
    expect(await screen.findByRole('heading',{name:'Contenido privado'})).toBeVisible()
    const key = Object.keys(sessionStorage).find(name=>name.startsWith('researcher:archived-owner-state:'))!
    const archive = JSON.parse(sessionStorage.getItem(key)!)
    expect(archive.entries['researcher:source-setup:v1:101']).toBe('exact unsent owner intent')
    expect(archive.additional.wikiDrafts).toEqual(before)
    expect(sessionStorage.getItem('researcher:source-setup:v1:101')).toBeNull()
    expect(fetch).toHaveBeenCalledTimes(1)
  } finally {fetch.mockRestore()}
})
