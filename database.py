import sqlite3
import os
import json
from datetime import datetime
from typing import List, Dict, Optional

import os

DB_PATH = os.environ.get('DATABASE_PATH', 'telemost_conferences.db')

def init_db():
    """Initialize the database with required tables"""
    # Ensure the directory for the database exists
    db_dir = os.path.dirname(DB_PATH)
    if db_dir and not os.path.exists(db_dir):
        os.makedirs(db_dir, exist_ok=True)

    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Create conferences table
    cursor.execute('''
        CREATE TABLE IF NOT EXISTS conferences (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            type TEXT NOT NULL CHECK(type IN ('conference', 'broadcast')),
            description TEXT,
            start_date DATE,
            start_time TIME,
            cohosts TEXT,
            create_calendar_event BOOLEAN DEFAULT 0,
            invite_users BOOLEAN DEFAULT 0,
            live_stream_title TEXT,
            live_stream_description TEXT,
            owner_id TEXT NOT NULL,
            owner_name TEXT NOT NULL,
            link TEXT UNIQUE,
            status TEXT DEFAULT 'scheduled',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    ''')
    
    # Create indexes for performance
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_owner_id ON conferences(owner_id)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_type ON conferences(type)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_status ON conferences(status)')
    cursor.execute('CREATE INDEX IF NOT EXISTS idx_created_at ON conferences(created_at)')
    
    # Create triggers to update the updated_at field
    cursor.execute('''
        CREATE TRIGGER IF NOT EXISTS update_conferences_updated_at 
        AFTER UPDATE ON conferences
        FOR EACH ROW
        BEGIN
            UPDATE conferences SET updated_at = CURRENT_TIMESTAMP WHERE id = NEW.id;
        END
    ''')
    
    conn.commit()
    conn.close()

def save_conference(conference_data: Dict) -> str:
    """
    Save a conference to the database
    Returns the ID of the saved conference
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    # Convert cohosts list to JSON string
    cohosts_str = json.dumps(conference_data.get('cohosts', []))
    
    # Prepare insert data
    data = (
        conference_data['name'],
        conference_data['type'],
        conference_data.get('description', ''),
        conference_data.get('startDate', ''),
        conference_data.get('startTime', ''),
        cohosts_str,
        conference_data.get('createCalendarEvent', False),
        conference_data.get('inviteUsers', False),
        conference_data.get('liveStreamTitle', ''),
        conference_data.get('liveStreamDescription', ''),
        conference_data['ownerId'],  # User who created the conference
        conference_data.get('ownerName', 'Unknown'),
        conference_data.get('link', ''),
        conference_data.get('status', 'scheduled')
    )
    
    # Insert conference
    cursor.execute('''
        INSERT INTO conferences
        (name, type, description, start_date, start_time, cohosts,
        create_calendar_event, invite_users, live_stream_title, live_stream_description,
        owner_id, owner_name, link, status)
        VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
    ''', data)

    conference_id = cursor.lastrowid

    conn.commit()
    conn.close()

    return str(conference_id)

def get_user_conferences(owner_id: str) -> List[Dict]:
    """
    Get conferences created by a specific user
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, type, description, start_date, start_time, 
               cohosts, create_calendar_event, invite_users,
               live_stream_title, live_stream_description,
               owner_id, owner_name, link, status, created_at
        FROM conferences 
        WHERE owner_id = ?
        ORDER BY created_at DESC
    ''', (owner_id,))
    
    rows = cursor.fetchall()
    conn.close()
    
    conferences = []
    for row in rows:
        cohosts = json.loads(row[6]) if row[6] else []
        conferences.append({
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'description': row[3],
            'startDate': row[4],
            'startTime': row[5],
            'cohosts': cohosts,
            'createCalendarEvent': bool(row[7]),
            'inviteUsers': bool(row[8]),
            'liveStreamTitle': row[9],
            'liveStreamDescription': row[10],
            'ownerId': row[11],
            'ownerName': row[12],
            'link': row[13],
            'status': row[14],
            'createdAt': row[15]
        })
    
    return conferences

def get_all_conferences() -> List[Dict]:
    """
    Get all conferences (for demo purposes)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, type, description, start_date, start_time, 
               cohosts, create_calendar_event, invite_users,
               live_stream_title, live_stream_description,
               owner_id, owner_name, link, status, created_at
        FROM conferences
        ORDER BY created_at DESC
    ''')
    
    rows = cursor.fetchall()
    conn.close()
    
    conferences = []
    for row in rows:
        cohosts = json.loads(row[6]) if row[6] else []
        conferences.append({
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'description': row[3],
            'startDate': row[4],
            'startTime': row[5],
            'cohosts': cohosts,
            'createCalendarEvent': bool(row[7]),
            'inviteUsers': bool(row[8]),
            'liveStreamTitle': row[9],
            'liveStreamDescription': row[10],
            'ownerId': row[11],
            'ownerName': row[12],
            'link': row[13],
            'status': row[14],
            'createdAt': row[15]
        })
    
    return conferences

def get_conference_by_id(conf_id: int) -> Optional[Dict]:
    """
    Get a specific conference by ID
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, type, description, start_date, start_time, 
               cohosts, create_calendar_event, invite_users,
               live_stream_title, live_stream_description,
               owner_id, owner_name, link, status, created_at
        FROM conferences
        WHERE id = ?
    ''', (conf_id,))
    
    row = cursor.fetchone()
    conn.close()
    
    if row:
        cohosts = json.loads(row[6]) if row[6] else []
        return {
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'description': row[3],
            'startDate': row[4],
            'startTime': row[5],
            'cohosts': cohosts,
            'createCalendarEvent': bool(row[7]),
            'inviteUsers': bool(row[8]),
            'liveStreamTitle': row[9],
            'liveStreamDescription': row[10],
            'ownerId': row[11],
            'ownerName': row[12],
            'link': row[13],
            'status': row[14],
            'createdAt': row[15]
        }
    
    return None

def update_conference(conf_id: int, conference_data: Dict) -> bool:
    """
    Update a conference in the database
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cohosts_str = json.dumps(conference_data.get('cohosts', []))
    
    cursor.execute('''
        UPDATE conferences SET
            name = ?,
            type = ?,
            description = ?,
            start_date = ?,
            start_time = ?,
            cohosts = ?,
            create_calendar_event = ?,
            invite_users = ?,
            live_stream_title = ?,
            live_stream_description = ?,
            owner_name = ?,
            link = ?,
            status = ?
        WHERE id = ?
    ''', (
        conference_data['name'],
        conference_data['type'],
        conference_data.get('description', ''),
        conference_data.get('startDate', ''),
        conference_data.get('startTime', ''),
        cohosts_str,
        conference_data.get('createCalendarEvent', False),
        conference_data.get('inviteUsers', False),
        conference_data.get('liveStreamTitle', ''),
        conference_data.get('liveStreamDescription', ''),
        conference_data.get('ownerName', 'Unknown'),
        conference_data.get('link', ''),
        conference_data.get('status', 'scheduled'),
        conf_id
    ))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success

def delete_conference(conf_id: int) -> bool:
    """
    Delete a conference from the database
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('DELETE FROM conferences WHERE id = ?', (conf_id,))
    
    success = cursor.rowcount > 0
    conn.commit()
    conn.close()
    
    return success

def get_conferences_by_type(conf_type: str) -> List[Dict]:
    """
    Get conferences filtered by type (conference or broadcast)
    """
    conn = sqlite3.connect(DB_PATH)
    cursor = conn.cursor()
    
    cursor.execute('''
        SELECT id, name, type, description, start_date, start_time, 
               cohosts, create_calendar_event, invite_users,
               live_stream_title, live_stream_description,
               owner_id, owner_name, link, status, created_at
        FROM conferences
        WHERE type = ?
        ORDER BY created_at DESC
    ''', (conf_type,))
    
    rows = cursor.fetchall()
    conn.close()
    
    conferences = []
    for row in rows:
        cohosts = json.loads(row[6]) if row[6] else []
        conferences.append({
            'id': row[0],
            'name': row[1],
            'type': row[2],
            'description': row[3],
            'startDate': row[4],
            'startTime': row[5],
            'cohosts': cohosts,
            'createCalendarEvent': bool(row[7]),
            'inviteUsers': bool(row[8]),
            'liveStreamTitle': row[9],
            'liveStreamDescription': row[10],
            'ownerId': row[11],
            'ownerName': row[12],
            'link': row[13],
            'status': row[14],
            'createdAt': row[15]
        })
    
    return conferences

# Initialize database when module is imported
if not os.path.exists(DB_PATH):
    init_db()