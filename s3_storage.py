"""
S3 Storage Module
Handles all persistent storage for GreenDial
Uses Digital Ocean Spaces (S3-compatible)
"""
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import config

# Initialize DO Spaces client (S3-compatible)
try:
    s3_client = boto3.client(
        's3',
        region_name=config.DO_SPACES_REGION,
        endpoint_url=config.DO_SPACES_ENDPOINT,
        aws_access_key_id=config.DO_SPACES_KEY,
        aws_secret_access_key=config.DO_SPACES_SECRET
    )
    print(f"[Storage] Initialized DO Spaces client: {config.DO_SPACES_BUCKET}/{config.S3_PREFIX}")
except Exception as e:
    print(f"[Storage] ERROR: Could not initialize DO Spaces client: {e}")
    s3_client = None


def _key(path):
    """Build full S3 key with prefix"""
    return f"{config.S3_PREFIX}{path}"


def _check_client():
    """Check if S3 client is available"""
    if s3_client is None:
        raise RuntimeError("DO Spaces client not initialized. Check configuration.")


# ============ USER DATA ============

def get_user(user_id):
    """Retrieve user data from DO Spaces"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_key(f"users/{user_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_user(user_id, data):
    """Save user data to DO Spaces"""
    _check_client()
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_key(f"users/{user_id}.json"),
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def delete_user(user_id):
    """Delete a user record and their conversation objects"""
    _check_client()
    s3_client.delete_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_key(f"users/{user_id}.json")
    )
    # Remove any conversation objects under this user's prefix
    resp = s3_client.list_objects_v2(
        Bucket=config.DO_SPACES_BUCKET,
        Prefix=_key(f"conversations/{user_id}/")
    )
    for obj in resp.get('Contents', []):
        s3_client.delete_object(Bucket=config.DO_SPACES_BUCKET, Key=obj['Key'])


def list_users():
    """List all user IDs"""
    _check_client()
    resp = s3_client.list_objects_v2(
        Bucket=config.DO_SPACES_BUCKET,
        Prefix=_key("users/")
    )
    users = []
    for obj in resp.get('Contents', []):
        key = obj['Key']
        if key.endswith('.json'):
            user_id = key.split('/')[-1].replace('.json', '')
            users.append(user_id)
    return users


# ============ CONVERSATIONS ============

def get_conversation(user_id, conversation_id):
    """Retrieve a conversation"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_key(f"conversations/{user_id}/{conversation_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_conversation(user_id, conversation_id, data):
    """Save a conversation"""
    _check_client()
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_key(f"conversations/{user_id}/{conversation_id}.json"),
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def list_conversations(user_id):
    """List all conversations for a user"""
    _check_client()
    resp = s3_client.list_objects_v2(
        Bucket=config.DO_SPACES_BUCKET,
        Prefix=_key(f"conversations/{user_id}/")
    )
    conversations = []
    for obj in resp.get('Contents', []):
        key = obj['Key']
        if key.endswith('.json'):
            conv_id = key.split('/')[-1].replace('.json', '')
            conversations.append({
                "id": conv_id,
                "last_modified": obj.get('LastModified', '').isoformat() if obj.get('LastModified') else None
            })
    return conversations


# ============ UNPROMPTED (GROUP FACILITATOR) ============

def _unprompted_key(path):
    return _key(f"unprompted/{path}")


def get_unprompted_participant(participant_id):
    """Retrieve unprompted participant by id"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_unprompted_key(f"participants/{participant_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_unprompted_participant(participant):
    """Save unprompted participant"""
    _check_client()
    participant_id = participant.get('participant_id')
    if not participant_id:
        raise ValueError("participant_id required")
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_unprompted_key(f"participants/{participant_id}.json"),
        Body=json.dumps(participant, indent=2),
        ContentType='application/json'
    )


def get_unprompted_campaign(campaign_id):
    """Retrieve campaign by id"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_unprompted_key(f"campaigns/{campaign_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_unprompted_campaign(campaign):
    """Persist campaign"""
    _check_client()
    campaign_id = campaign.get('campaign_id')
    if not campaign_id:
        raise ValueError("campaign_id required")
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_unprompted_key(f"campaigns/{campaign_id}.json"),
        Body=json.dumps(campaign, indent=2),
        ContentType='application/json'
    )


def list_unprompted_campaigns():
    """List all campaigns (loads minimal metadata)"""
    _check_client()
    resp = s3_client.list_objects_v2(
        Bucket=config.DO_SPACES_BUCKET,
        Prefix=_unprompted_key("campaigns/")
    )
    campaigns = []
    for obj in resp.get('Contents', []):
        key = obj['Key']
        if key.endswith('.json'):
            cid = key.split('/')[-1].replace('.json', '')
            campaign = get_unprompted_campaign(cid)
            if campaign:
                campaigns.append(campaign)
    return campaigns


def get_unprompted_group(group_id):
    """Retrieve facilitator group"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_unprompted_key(f"groups/{group_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_unprompted_group(group):
    """Save facilitator group"""
    _check_client()
    group_id = group.get('group_id')
    if not group_id:
        raise ValueError("group_id required")
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_unprompted_key(f"groups/{group_id}.json"),
        Body=json.dumps(group, indent=2),
        ContentType='application/json'
    )


# ============ FEEDBACK ============

def get_feedback():
    """Get all public feedback posts"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_key("feedback/posts.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return []
        raise


def save_feedback(posts):
    """Persist feedback posts list"""
    _check_client()
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_key("feedback/posts.json"),
        Body=json.dumps(posts, indent=2),
        ContentType='application/json'
    )


# ============ STICKER BOARD ============

def get_sticker_board(user_id):
    """Retrieve a user's sticker board."""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_key(f"stickers/{user_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_sticker_board(user_id, data):
    """Save a user's sticker board."""
    _check_client()
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_key(f"stickers/{user_id}.json"),
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def get_sticker_token(token):
    """Look up user_id from a share token."""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_key(f"stickers/tokens/{token}.json")
        )
        data = json.loads(resp['Body'].read().decode('utf-8'))
        return data.get('user_id')
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_sticker_token(token, user_id):
    """Store a share token → user_id mapping."""
    _check_client()
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_key(f"stickers/tokens/{token}.json"),
        Body=json.dumps({'user_id': user_id}),
        ContentType='application/json'
    )


# ============ BOUNTIES ============

def get_bounties():
    """Get all bounties"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.DO_SPACES_BUCKET,
            Key=_key("bounties/bounties.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return []
        raise


def save_bounties(bounties):
    """Persist bounties list"""
    _check_client()
    s3_client.put_object(
        Bucket=config.DO_SPACES_BUCKET,
        Key=_key("bounties/bounties.json"),
        Body=json.dumps(bounties, indent=2),
        ContentType='application/json'
    )
