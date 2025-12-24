"""
S3 Storage Module
Handles all persistent storage for GreenDial
"""
import json
import boto3
from botocore.exceptions import ClientError, NoCredentialsError
import config

# Initialize S3 client
try:
    if config.AWS_ACCESS_KEY_ID and config.AWS_SECRET_ACCESS_KEY:
        s3_client = boto3.client(
            's3',
            region_name=config.AWS_REGION,
            aws_access_key_id=config.AWS_ACCESS_KEY_ID,
            aws_secret_access_key=config.AWS_SECRET_ACCESS_KEY
        )
    else:
        # Use default credentials (IAM role, env vars, etc.)
        s3_client = boto3.client('s3', region_name=config.AWS_REGION)
except Exception as e:
    print(f"[S3] Warning: Could not initialize S3 client: {e}")
    s3_client = None


def _key(path):
    """Build full S3 key with prefix"""
    return f"{config.S3_PREFIX}{path}"


def _check_client():
    """Check if S3 client is available"""
    if s3_client is None:
        raise RuntimeError("S3 client not initialized. Check AWS credentials.")


# ============ USER DATA ============

def get_user(user_id):
    """Retrieve user data from S3"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.S3_BUCKET,
            Key=_key(f"users/{user_id}.json")
        )
        return json.loads(resp['Body'].read().decode('utf-8'))
    except ClientError as e:
        if e.response['Error']['Code'] == 'NoSuchKey':
            return None
        raise


def save_user(user_id, data):
    """Save user data to S3"""
    _check_client()
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(f"users/{user_id}.json"),
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def list_users():
    """List all user IDs"""
    _check_client()
    resp = s3_client.list_objects_v2(
        Bucket=config.S3_BUCKET,
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
    _check_client()
    s3_client.put_object(
        Bucket=config.S3_BUCKET,
        Key=_key(f"conversations/{user_id}/{conversation_id}.json"),
        Body=json.dumps(data, indent=2),
        ContentType='application/json'
    )


def list_conversations(user_id):
    """List all conversations for a user"""
    _check_client()
    resp = s3_client.list_objects_v2(
        Bucket=config.S3_BUCKET,
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
            Bucket=config.S3_BUCKET,
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
        Bucket=config.S3_BUCKET,
        Key=_unprompted_key(f"participants/{participant_id}.json"),
        Body=json.dumps(participant, indent=2),
        ContentType='application/json'
    )


def get_unprompted_campaign(campaign_id):
    """Retrieve campaign by id"""
    _check_client()
    try:
        resp = s3_client.get_object(
            Bucket=config.S3_BUCKET,
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
        Bucket=config.S3_BUCKET,
        Key=_unprompted_key(f"campaigns/{campaign_id}.json"),
        Body=json.dumps(campaign, indent=2),
        ContentType='application/json'
    )


def list_unprompted_campaigns():
    """List all campaigns (loads minimal metadata)"""
    _check_client()
    resp = s3_client.list_objects_v2(
        Bucket=config.S3_BUCKET,
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
            Bucket=config.S3_BUCKET,
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
        Bucket=config.S3_BUCKET,
        Key=_unprompted_key(f"groups/{group_id}.json"),
        Body=json.dumps(group, indent=2),
        ContentType='application/json'
    )
