#!/usr/bin/env python3
"""
Test the enhanced Doc V2 conversation system
"""
import json
import sys
sys.path.insert(0, '.')

import handlers
from prompts import doc_v2

def simulate_conversation():
    """Simulate a full conversation to test guided profile building"""
    
    # Create test user
    test_user = {
        'user_id': 'user_docv2_test',
        'username': 'TestPatient',
        'passphrase': 'test',
        'profile': {},
        'transcript': '',
        'settings': {}
    }
    handlers._cache_user('user_docv2_test', test_user)
    
    conversation = [
        "Hi, I have diabetes and I'm struggling to manage it",
        "I was diagnosed about 2 years ago. My blood sugar has been high lately",
        "I take metformin 500mg twice daily",
        "I'm 45 years old",
        "I feel tired all the time and get headaches"
    ]
    
    print("=" * 60)
    print("ENHANCED DOC CONVERSATION SIMULATION")
    print("=" * 60)
    print()
    
    for i, user_msg in enumerate(conversation, 1):
        print(f"Turn {i}:")
        print(f"User: {user_msg}")
        print()
        
        request = {
            'user_id': 'user_docv2_test',
            'text': user_msg
        }
        
        try:
            response_json = handlers.handle_chat(request)
            data = json.loads(response_json)
            
            # Show Doc's response
            doc_response = data.get('response', '')
            print(f"Doc: {doc_response}")
            print()
            
            # Show profile updates
            if data.get('profile_updated'):
                profile = data.get('profile', {})
                print(f"[PROFILE UPDATED]")
                for key, value in profile.items():
                    print(f"  - {key}: {value}")
                print()
            
            # Show conversation stage
            current_user = handlers.get_user_data('user_docv2_test')
            stage = doc_v2.get_conversation_stage(current_user.get('profile', {}))
            missing = doc_v2.get_priority_missing_fields(current_user.get('profile', {}))
            print(f"[STAGE: {stage}]")
            if missing:
                print(f"[MISSING: {', '.join([f[0] for f in missing[:3]])}]")
            print()
            print("-" * 60)
            print()
            
        except Exception as e:
            print(f"Error: {e}")
            import traceback
            traceback.print_exc()
            break
    
    # Final profile summary
    final_user = handlers.get_user_data('user_docv2_test')
    print("=" * 60)
    print("FINAL PROFILE")
    print("=" * 60)
    print(json.dumps(final_user.get('profile', {}), indent=2))
    print()
    
    # Analyze completeness
    profile = final_user.get('profile', {})
    total_fields = len(doc_v2.PROFILE_FIELDS)
    filled_fields = sum(1 for k, v in profile.items() if v)
    completeness = (filled_fields / total_fields) * 100
    print(f"Profile Completeness: {completeness:.1f}% ({filled_fields}/{total_fields} fields)")
    print()
    
    stage = doc_v2.get_conversation_stage(profile)
    print(f"Conversation Stage: {stage}")
    print()

if __name__ == '__main__':
    simulate_conversation()
