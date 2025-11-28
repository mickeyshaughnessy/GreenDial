"""
S3 Storage Module - Worker Droid Implementation
Handles all persistent storage for GreenDial at s3://mithrilmedia/greendial/
"""
import json
import boto3
from botocore.exceptions import ClientError
import config

s3_client = boto3.client(
    's3',
    region_name=config.AWS_REGION,
    aws_access_key_id=config.AWS_ACCESS_KEY_ID,
    aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
)

def _key(path):
    """Build full S3 key with prefix"""
    return f"{config.S3_PREFIX}{path}"

# User Data
def get_user(user_id):
    """Retrieve user data from S3"""
    try:
        resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=_key(f"users/{user_id}.json"))
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise

def save_user(user_id, data):
    """Save user data to S3"""
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(f"users/{user_id}.json"),
        Body=json.dumps(data),
        ContentType='application/json'
    )

def list_users():
    """List all user IDs"""
    resp = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=_key("users/"))
    users = []
    for obj in resp.get('Contents', []):
        key = obj['Key']
        if key.endswith('.json'):
            user_id = key.split('/')[-1].replace('.json', '')
            users.append(user_id)
    return users

# Conversations
def get_conversation(user_id, conversation_id):
    """Retrieve a conversation"""
    try:
        resp = s3_client.get_object(
            Bucket=config.S3_BUCKET, 
            Key=_key(f"conversations/{user_id}/{conversation_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise

def save_conversation(user_id, conversation_id, data):
    """Save a conversation"""
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(f"conversations/{user_id}/{conversation_id}.json"),
        Body=json.dumps(data),
        ContentType='application/json'
    )

def list_conversations(user_id):
    """List all conversations for a user"""
    resp = s3_client.list_objects_v2(
        Bucket=config.S3_BUCKET, 
        Prefix=_key(f"conversations/{user_id}/")
    )
    conversations = []
    for obj in resp.get('Contents', []):
        key = obj['Key']
        if key.endswith('.json'):
            conv_id = key.split('/')[-1].replace('.json', '')
            conversations.append(conv_id)
    return conversations

# Health Records
def save_health_record(user_id, record_type, timestamp, data):
    """Save a health data record (INSERT symbol handler)"""
    record = {
        "type": record_type,
        "timestamp": timestamp,
        "data": data
    }
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(f"health/{user_id}/{record_type}/{timestamp}.json"),
        Body=json.dumps(record),
        ContentType='application/json'
    )

def query_health_records(user_id, record_type=None, start_date=None, end_date=None):
    """Query health records (SELECT symbol handler)"""
    prefix = _key(f"health/{user_id}/")
    if record_type:
        prefix += f"{record_type}/"
    
    resp = s3_client.list_objects_v2(Bucket=config.S3_BUCKET, Prefix=prefix)
    records = []
    
    for obj in resp.get('Contents', []):
        try:
            record_resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=obj['Key'])
            record = json.loads(record_resp['Body'].read().decode('utf-8'))
            records.append(record)
        except:
            continue
    
    return records

# Goals
def get_goals(user_id):
    """Get user goals"""
    try:
        resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=_key(f"goals/{user_id}.json"))
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return {"goals": []}
        raise

def save_goals(user_id, goals):
    """Save user goals"""
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(f"goals/{user_id}.json"),
        Body=json.dumps(goals),
        ContentType='application/json'
    )

# Settings
def get_settings(user_id):
    """Get user settings"""
    try:
        resp = s3_client.get_object(Bucket=config.S3_BUCKET, Key=_key(f"settings/{user_id}.json"))
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return {}
        raise

def save_settings(user_id, settings):
    """Save user settings"""
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(f"settings/{user_id}.json"),
        Body=json.dumps(settings),
        ContentType='application/json'
    )
