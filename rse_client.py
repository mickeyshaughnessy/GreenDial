"""
RSE Client - The Services Exchange API Integration
Submits service requests and receives bids from providers

RSE is an external marketplace where users can request services
(food delivery, cleaning, landscaping, etc.) and providers bid on them.

API: https://rse-api.com:5003/
Docs: https://theservicesexchange.com/api_docs.html
"""
import requests
import json
from datetime import datetime
import config

RSE_API_URL = getattr(config, 'RSE_API_URL', 'https://rse-api.com:5003')

# Service categories that make sense for RSE bidding
RSE_SERVICE_CATEGORIES = [
    'food_delivery',
    'meal_prep',
    'cleaning',
    'landscaping',
    'personal_training',
    'massage',
    'grocery_delivery',
    'pet_care',
    'errands',
    'home_maintenance'
]

def submit_bid_request(user_id, service_type, description, budget=None, location=None, deadline=None):
    """
    Submit a service request to RSE for providers to bid on
    
    Args:
        user_id: GreenDial user ID
        service_type: Type of service (food_delivery, cleaning, etc.)
        description: What the user needs
        budget: Optional budget limit
        location: User's location
        deadline: When service is needed
    
    Returns:
        dict with request_id if successful, error otherwise
    """
    try:
        payload = {
            'client_id': f'greendial_{user_id}',
            'service_type': service_type,
            'description': description,
            'source': 'greendial',
            'timestamp': datetime.utcnow().isoformat()
        }
        
        if budget:
            payload['budget'] = budget
        if location:
            payload['location'] = location
        if deadline:
            payload['deadline'] = deadline
        
        response = requests.post(
            f"{RSE_API_URL}/submit_bid",
            json=payload,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return {
                'success': True,
                'request_id': data.get('request_id'),
                'message': data.get('message', 'Bid request submitted')
            }
        else:
            return {
                'success': False,
                'error': f"RSE API error: {response.status_code}"
            }
            
    except requests.exceptions.RequestException as e:
        print(f"RSE API connection error: {e}")
        return {'success': False, 'error': str(e)}
    except Exception as e:
        print(f"RSE client error: {e}")
        return {'success': False, 'error': str(e)}

def get_bids_for_request(request_id):
    """
    Get bids received for a specific service request
    
    Args:
        request_id: The RSE request ID
    
    Returns:
        List of bids from providers
    """
    try:
        response = requests.get(
            f"{RSE_API_URL}/bids/{request_id}",
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('bids', [])
        return []
        
    except Exception as e:
        print(f"Error fetching bids: {e}")
        return []

def get_user_requests(user_id):
    """
    Get all service requests for a user
    
    Args:
        user_id: GreenDial user ID
    
    Returns:
        List of request objects with their bids
    """
    try:
        response = requests.get(
            f"{RSE_API_URL}/requests",
            params={'client_id': f'greendial_{user_id}'},
            timeout=10
        )
        
        if response.status_code == 200:
            return response.json().get('requests', [])
        return []
        
    except Exception as e:
        print(f"Error fetching user requests: {e}")
        return []

def is_rse_service(suggestion_text):
    """
    Determine if a suggestion should be submitted to RSE
    
    Args:
        suggestion_text: The suggestion text from Doc
    
    Returns:
        tuple of (bool, service_type) - whether it's an RSE service and what type
    """
    text_lower = suggestion_text.lower()
    
    service_keywords = {
        'food_delivery': ['food delivery', 'deliver food', 'order food', 'meal delivery', 'get food delivered'],
        'meal_prep': ['meal prep', 'prepared meals', 'cook meals', 'meal preparation'],
        'cleaning': ['cleaning service', 'house cleaning', 'clean your home', 'maid service', 'cleaning help'],
        'landscaping': ['landscaping', 'lawn care', 'yard work', 'garden', 'mowing'],
        'personal_training': ['personal trainer', 'fitness trainer', 'workout trainer', 'hire a trainer'],
        'massage': ['massage', 'massage therapy', 'therapeutic massage'],
        'grocery_delivery': ['grocery delivery', 'groceries delivered', 'deliver groceries'],
        'pet_care': ['pet sitter', 'dog walker', 'pet care', 'pet sitting'],
        'errands': ['run errands', 'errand service', 'help with errands'],
        'home_maintenance': ['handyman', 'home repair', 'fix things', 'maintenance']
    }
    
    for service_type, keywords in service_keywords.items():
        if any(kw in text_lower for kw in keywords):
            return True, service_type
    
    return False, None

def extract_service_details(suggestion_text, user_profile):
    """
    Extract service request details from a suggestion
    
    Args:
        suggestion_text: The suggestion from Doc
        user_profile: User's profile for location/budget
    
    Returns:
        dict with service details
    """
    is_service, service_type = is_rse_service(suggestion_text)
    
    if not is_service:
        return None
    
    return {
        'service_type': service_type,
        'description': suggestion_text,
        'location': user_profile.get('location'),
        'budget': user_profile.get('budget')
    }
