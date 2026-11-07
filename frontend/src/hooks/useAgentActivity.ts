/** Expose recent activity and its connection evidence to the owner drawer. @module */
import {useActivityFeedStore} from '../stores/activityFeed'

/** Keep an empty list distinct from a disconnected or incomplete history. */
export function useAgentActivity(){
 const events=useActivityFeedStore(state=>state.events)
 const clearFeed=useActivityFeedStore(state=>state.clearFeed)
 const connection=useActivityFeedStore(state=>state.connection)
 const gap=useActivityFeedStore(state=>state.gap)
 return {events,clearFeed,connection,gap}
}
