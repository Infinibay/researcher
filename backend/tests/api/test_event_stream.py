"""Exercise authenticated HTTP and WebSocket replay through the actual application boundary."""

import json


def append_events(conn, count, project=1):
    """Write real committed rows while owner transports connect, disconnect and recover."""
    ids = []
    for index in range(count):
        ids.append(conn.execute("INSERT INTO events_log(project_id,event_type,event_source,event_data_json,created_at) VALUES(?,'test.observed','test',?,'2026-11-07 00:00:00')", (project, json.dumps({"index":index}))).lastrowid)
    conn.commit()
    return ids


def test_owner_http_and_websocket_recover_concurrent_history_once(client, seeded_project, db_conn):
    """After reading only one page, reconnect recovers old and concurrent rows without any execution."""
    append_events(db_conn, 237)
    db_conn.execute("INSERT INTO projects(id,name) VALUES(2,'Other project')")
    db_conn.commit()
    append_events(db_conn, 3, 2)
    expected = [row[0] for row in db_conn.execute("SELECT id FROM events_log WHERE project_id=1 ORDER BY id")]
    path = 'ws://localhost/ws?project_id=1&after_id=0'
    with client.websocket_connect(path, headers={'Origin':'http://localhost'}) as socket:
        first = socket.receive_json()
        assert first['has_more'] is True and len(first['events']) == 100
        found = [int(event['event_id']) for event in first['events']]
        cursor = first['next_after_id']
    expected += append_events(db_conn, 15)
    with client.websocket_connect('ws://localhost/ws?project_id=1&after_id='+cursor, headers={'Origin':'http://localhost'}) as socket:
        second = socket.receive_json()
        found += [int(event['event_id']) for event in second['events']]
        expected += append_events(db_conn, 23)
        while found[-1] != expected[-1]:
            page = socket.receive_json()
            assert all(event['project_id'] == 1 for event in page['events'])
            found += [int(event['event_id']) for event in page['events']]
    assert found == expected and len(set(found)) == len(found)
    response = client.get('/api/events/1?limit=100')
    assert response.headers['cache-control'] == 'no-store'
    assert response.json()['events'] == first['events']
    assert client.get('/api/events/1?after_id=-1').status_code == 422
    assert db_conn.execute('SELECT count(*) FROM runtime_inference_dispatches').fetchone()[0] == 0


def test_owner_socket_explains_expired_cursor_and_continues_after_retention_floor(client, seeded_project, db_conn):
    """Known event deletion produces a visible reset requirement followed by remaining durable rows."""
    ids = append_events(db_conn, 5)
    db_conn.execute('DELETE FROM events_log WHERE id=?', (ids[2],))
    db_conn.commit()
    with client.websocket_connect('ws://localhost/ws?project_id=1&after_id='+str(ids[0]), headers={'Origin':'http://localhost'}) as socket:
        reset = socket.receive_json()
        assert reset['reset_required'] is True and reset['reset_reason'] == 'retention'
        assert reset['resume_after_id'] == str(ids[2]) and reset['events'] == []
        page = socket.receive_json()
        assert [int(item['event_id']) for item in page['events']] == ids[3:]
    assert client.get('/api/events/1?after_id='+str(ids[0])).json()['reset_required'] is True


def test_event_payload_damage_is_explicit_and_large_ids_survive_http(client, seeded_project, db_conn):
    """An unavailable historical payload stays marked unknown and cannot round its durable identity."""
    identifier = 9007199254740993
    db_conn.execute("INSERT INTO events_log(id,project_id,event_type,event_source,event_data_json) VALUES(?,1,'test.damaged','test','{bad')", (identifier,))
    db_conn.commit()
    response = client.get('/api/events/1?after_id='+str(identifier-1)).json()
    event = response['events'][0]
    assert event['event_id'] == response['next_after_id'] == str(identifier)
    assert event['data'] is None and event['data_unavailable'] is True
