"""
Analyze debug response file and extract relevant information
"""

import json
import sys
import glob

def analyze_debug_file():
    """Analyze the debug response and show key information"""
    
    # Find the most recent debug file
    debug_files = glob.glob("debug_response_*.txt")
    
    if not debug_files:
        print("❌ No debug files found")
        return
    
    # Get the most recent one
    debug_file = sorted(debug_files)[-1]
    print(f"📄 Analyzing: {debug_file}\n")
    
    with open(debug_file, 'r') as f:
        content = f.read()
    
    print(f"📊 File size: {len(content):,} characters\n")
    
    # Split by WebSocket delimiter
    messages = content.split('~m~')
    
    print(f"📦 Total messages: {len(messages)}\n")
    
    # Analyze message types
    message_types = {}
    json_messages = []
    
    for msg in messages:
        if not msg or msg.isdigit():
            continue
        
        try:
            data = json.loads(msg)
            if 'm' in data:
                msg_type = data['m']
                message_types[msg_type] = message_types.get(msg_type, 0) + 1
                
                # Keep interesting messages
                if msg_type not in ['ping', 'qsd']:
                    json_messages.append(data)
        except:
            pass
    
    print("📋 Message Types Found:")
    for msg_type, count in sorted(message_types.items()):
        print(f"   {msg_type}: {count}")
    
    print(f"\n📝 Sample Messages (first 3 interesting ones):\n")
    
    for i, msg in enumerate(json_messages[:3]):
        print(f"Message {i+1}:")
        print(f"  Type: {msg.get('m', 'unknown')}")
        
        if 'p' in msg:
            params = msg['p']
            print(f"  Params count: {len(params)}")
            
            # Show structure of first param
            if params and len(params) > 0:
                first_param = params[0]
                print(f"  First param type: {type(first_param).__name__}")
                
                if len(params) > 1:
                    second_param = params[1]
                    print(f"  Second param type: {type(second_param).__name__}")
                    
                    if isinstance(second_param, dict):
                        print(f"  Second param keys: {list(second_param.keys())}")
                        
                        # Look for data arrays
                        for key in ['s', 'ns', 'd', 'lbs', 'data']:
                            if key in second_param:
                                data_item = second_param[key]
                                print(f"  Found '{key}' key!")
                                print(f"    Type: {type(data_item).__name__}")
                                
                                if isinstance(data_item, list) and len(data_item) > 0:
                                    print(f"    Length: {len(data_item)}")
                                    print(f"    First item: {str(data_item[0])[:200]}")
                                elif isinstance(data_item, dict):
                                    print(f"    Keys: {list(data_item.keys())}")
        
        print(f"  Full message (first 500 chars):")
        print(f"    {str(msg)[:500]}")
        print()
    
    # Look specifically for timescale_update or du messages
    print("\n🔍 Looking for data messages (timescale_update, du, series_loading)...\n")
    
    data_messages = [m for m in json_messages if m.get('m') in ['timescale_update', 'du', 'series_loading']]
    
    if data_messages:
        print(f"✅ Found {len(data_messages)} data messages!")
        print("\nFirst data message structure:")
        print(json.dumps(data_messages[0], indent=2)[:1000])
    else:
        print("❌ No data messages found")
        print("\nAll message types we saw:")
        print(list(message_types.keys()))


if __name__ == "__main__":
    analyze_debug_file()