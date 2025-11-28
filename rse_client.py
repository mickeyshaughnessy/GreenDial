"""
RSE Client - The Services Exchange API Integration
Fetches service bids for diet, exercise, sleep, and entertainment
API Documentation: https://theservicesexchange.com/api_docs.html
"""
import requests
import json
from datetime import datetime
import config

RSE_CATEGORIES = ['diet', 'exercise', 'sleep', 'entertainment']

def get_bids(category=None, location=None, max_results=10):
    """
    Fetch service bids from RSE API
    
    Args:
        category: One of diet, exercise, sleep, entertainment (or None for all)
        location: User location for nearby services
        max_results: Maximum number of results to return
    
    Returns:
        List of bid objects
    """
    try:
        params = {
            'limit': max_results
        }
        
        if category and category in RSE_CATEGORIES:
            params['category'] = category
        
        if location:
            params['location'] = location
        
        response = requests.get(
            f"{config.RSE_API_URL}/bids",
            params=params,
            timeout=10
        )
        
        if response.status_code == 200:
            data = response.json()
            return data.get('bids', [])
        else:
            print(f"RSE API error: {response.status_code}")
            return []
            
    except requests.exceptions.RequestException as e:
        print(f"RSE API connection error: {e}")
        return []
    except Exception as e:
        print(f"RSE client error: {e}")
        return []

def get_suggestions_for_user(user_profile, categories=None):
    """
    Get personalized service suggestions based on user profile
    
    Args:
        user_profile: User's profile data including goals, preferences
        categories: List of categories to fetch (default: all)
    
    Returns:
        Dict with suggestions by category
    """
    categories = categories or RSE_CATEGORIES
    suggestions = {}
    
    location = user_profile.get('location', '')
    
    for category in categories:
        bids = get_bids(category=category, location=location, max_results=5)
        
        # Score and rank bids based on user profile
        scored_bids = []
        for bid in bids:
            score = calculate_relevance_score(bid, user_profile, category)
            scored_bids.append({
                **bid,
                'relevance_score': score
            })
        
        # Sort by relevance
        scored_bids.sort(key=lambda x: x.get('relevance_score', 0), reverse=True)
        suggestions[category] = scored_bids[:3]  # Top 3 per category
    
    return suggestions

def calculate_relevance_score(bid, user_profile, category):
    """
    Calculate how relevant a bid is for the user
    
    Args:
        bid: The service bid
        user_profile: User's profile
        category: The category of the bid
    
    Returns:
        Score from 0-100
    """
    score = 50  # Base score
    
    goals = user_profile.get('goals', [])
    preferences = user_profile.get('preferences', {})
    
    # Check if bid matches user goals
    bid_description = bid.get('description', '').lower()
    bid_title = bid.get('title', '').lower()
    
    for goal in goals:
        goal_text = goal.get('text', '').lower() if isinstance(goal, dict) else str(goal).lower()
        if any(word in bid_description or word in bid_title for word in goal_text.split()):
            score += 15
    
    # Category-specific scoring
    if category == 'diet':
        if preferences.get('diet_type'):
            if preferences['diet_type'].lower() in bid_description:
                score += 20
    
    elif category == 'exercise':
        if preferences.get('fitness_level'):
            level = preferences['fitness_level'].lower()
            if level in bid_description:
                score += 20
    
    elif category == 'sleep':
        if preferences.get('sleep_issues'):
            for issue in preferences.get('sleep_issues', []):
                if issue.lower() in bid_description:
                    score += 10
    
    # Price consideration
    budget = preferences.get('budget', 'medium')
    bid_price = bid.get('price', 0)
    
    if budget == 'low' and bid_price < 50:
        score += 10
    elif budget == 'high' and bid_price > 100:
        score += 5
    
    # Rating boost
    rating = bid.get('rating', 0)
    score += int(rating * 5)
    
    return min(100, max(0, score))

def format_suggestion_message(suggestions):
    """
    Format suggestions into a human-readable message for Doc
    
    Args:
        suggestions: Dict of suggestions by category
    
    Returns:
        Formatted string for Doc to present
    """
    if not any(suggestions.values()):
        return "I don't have any service suggestions available right now."
    
    lines = ["Here are some personalized service suggestions for you:\n"]
    
    category_labels = {
        'diet': 'Nutrition & Diet',
        'exercise': 'Fitness & Exercise', 
        'sleep': 'Sleep & Recovery',
        'entertainment': 'Wellness & Entertainment'
    }
    
    for category, bids in suggestions.items():
        if bids:
            lines.append(f"\n**{category_labels.get(category, category)}:**")
            for i, bid in enumerate(bids[:2], 1):
                title = bid.get('title', 'Service')
                price = bid.get('price', 'N/A')
                rating = bid.get('rating', 'N/A')
                lines.append(f"  {i}. {title} - ${price} (Rating: {rating}/5)")
    
    lines.append("\nWould you like more details on any of these?")
    
    return '\n'.join(lines)

# Mock data for development/testing when RSE API is unavailable
MOCK_BIDS = {
    'diet': [
        {'id': 'd1', 'title': 'Personalized Meal Planning', 'description': 'Custom meal plans based on your goals', 'price': 49, 'rating': 4.5, 'provider': 'NutriPlan'},
        {'id': 'd2', 'title': 'Healthy Meal Delivery', 'description': 'Fresh prepared meals delivered daily', 'price': 199, 'rating': 4.2, 'provider': 'FreshBox'},
        {'id': 'd3', 'title': 'Nutrition Coaching Session', 'description': '1-on-1 session with certified nutritionist', 'price': 75, 'rating': 4.8, 'provider': 'HealthFirst'},
    ],
    'exercise': [
        {'id': 'e1', 'title': 'Personal Training Session', 'description': 'One hour with certified trainer', 'price': 60, 'rating': 4.7, 'provider': 'FitLife'},
        {'id': 'e2', 'title': 'Monthly Gym Membership', 'description': 'Full access to equipment and classes', 'price': 45, 'rating': 4.3, 'provider': 'PowerGym'},
        {'id': 'e3', 'title': 'Online Fitness Program', 'description': '12-week guided workout program', 'price': 99, 'rating': 4.4, 'provider': 'HomeGains'},
    ],
    'sleep': [
        {'id': 's1', 'title': 'Sleep Consultation', 'description': 'Assessment with sleep specialist', 'price': 120, 'rating': 4.6, 'provider': 'RestWell'},
        {'id': 's2', 'title': 'Meditation App Premium', 'description': 'Guided sleep meditations', 'price': 12, 'rating': 4.5, 'provider': 'CalmMind'},
        {'id': 's3', 'title': 'Sleep Tracking Device', 'description': 'Advanced sleep monitoring', 'price': 149, 'rating': 4.1, 'provider': 'SleepTech'},
    ],
    'entertainment': [
        {'id': 'n1', 'title': 'Wellness Retreat Day Pass', 'description': 'Spa, yoga, and relaxation', 'price': 85, 'rating': 4.8, 'provider': 'ZenSpace'},
        {'id': 'n2', 'title': 'Outdoor Adventure Tour', 'description': 'Hiking and nature experience', 'price': 55, 'rating': 4.6, 'provider': 'TrailBlazers'},
        {'id': 'n3', 'title': 'Cooking Class', 'description': 'Learn healthy cooking techniques', 'price': 45, 'rating': 4.4, 'provider': 'ChefSkills'},
    ]
}

def get_mock_bids(category=None):
    """Return mock bids for testing"""
    if category and category in MOCK_BIDS:
        return MOCK_BIDS[category]
    
    all_bids = []
    for cat_bids in MOCK_BIDS.values():
        all_bids.extend(cat_bids)
    return all_bids

def get_suggestions_mock(user_profile):
    """Get mock suggestions for testing"""
    suggestions = {}
    for category in RSE_CATEGORIES:
        bids = MOCK_BIDS.get(category, [])
        scored_bids = []
        for bid in bids:
            score = calculate_relevance_score(bid, user_profile, category)
            scored_bids.append({**bid, 'relevance_score': score})
        scored_bids.sort(key=lambda x: x['relevance_score'], reverse=True)
        suggestions[category] = scored_bids
    return suggestions
