#!/usr/bin/env python3
"""
Script to insert usage validation code into silence_cutter.py
"""

def fix_usage_validation():
    print("🔧 Fixing usage validation in process_video method...")
    
    # Read the current file
    with open('silence_cutter.py', 'r', encoding='utf-8') as f:
        lines = f.readlines()
    
    # Find the process_video method and the line where we need to insert
    target_line = None
    in_process_video = False
    
    for i, line in enumerate(lines):
        if 'def process_video(self):' in line:
            in_process_video = True
            print(f"📍 Found process_video method at line {i + 1}")
        
        if in_process_video and '# Get selected silent parts' in line:
            target_line = i
            print(f"📍 Found insertion point at line {i + 1}")
            break
    
    if target_line is None:
        print("❌ Could not find insertion point")
        return False
    
    # Define the usage validation code
    validation_code = '''        # Check usage limits before processing
        if API_COMMUNICATION_AVAILABLE:
            try:
                # Calculate file duration properly
                duration_minutes = 1  # Default fallback
                
                # Try to get actual duration from video player
                if hasattr(self, 'video_player') and hasattr(self.video_player, 'duration_seconds'):
                    duration_minutes = self.video_player.duration_seconds / 60
                    print(f"🎥 Using video player duration: {duration_minutes:.2f} minutes")
                else:
                    # Fallback: Use file size estimation
                    try:
                        file_size_bytes = os.path.getsize(self.video_path)
                        duration_minutes = max(1, file_size_bytes / (1024 * 1024))
                        print(f"📊 Using file size estimation: {duration_minutes:.2f} minutes")
                    except Exception as e:
                        print(f"⚠️ Duration calculation failed: {e}")
                        duration_minutes = 1
                
                # Validate usage before processing
                validation_result = api_client.validate_file_usage(
                    file_duration_minutes=duration_minutes
                )
                
                if not validation_result.get('allowed', False):
                    message = validation_result.get('message', 'Usage limit exceeded')
                    remaining = validation_result.get('remainingMinutes', 0)
                    
                    # Create upgrade message with specific details
                    upgrade_message = f"{message}\\n\\n"
                    if remaining > 0:
                        upgrade_message += f"You have {remaining:.1f} minutes remaining this month.\\n"
                    else:
                        upgrade_message += "You have reached your monthly limit.\\n"
                    
                    upgrade_message += "Upgrade to a paid plan for unlimited processing!"
                    
                    # Show usage limit dialog
                    msg_box = QMessageBox()
                    msg_box.setIcon(QMessageBox.Warning)
                    msg_box.setWindowTitle("Usage Limit Exceeded")
                    msg_box.setText(upgrade_message)
                    
                    # Add upgrade button
                    upgrade_btn = msg_box.addButton("🚀 Upgrade Now", QMessageBox.ActionRole)
                    cancel_btn = msg_box.addButton("Cancel", QMessageBox.RejectRole)
                    msg_box.setDefaultButton(upgrade_btn)
                    
                    result = msg_box.exec_()
                    
                    # Open upgrade page if user clicks upgrade
                    if msg_box.clickedButton() == upgrade_btn:
                        self.open_help_upgrade()
                    
                    return  # Stop processing
                    
                print(f"✅ Usage validation passed: {validation_result.get('message', 'OK')}")
                
            except Exception as e:
                print(f"⚠️ Usage validation failed: {e}")
                # Show warning but allow processing in offline mode
                msg_box = QMessageBox()
                msg_box.setIcon(QMessageBox.Warning) 
                msg_box.setWindowTitle("Offline Mode")
                msg_box.setText("Unable to verify usage limits (offline mode).\\n\\nProcessing will continue but may not count towards your quota until you're back online.")
                msg_box.setStandardButtons(QMessageBox.Ok | QMessageBox.Cancel)
                
                if msg_box.exec_() == QMessageBox.Cancel:
                    return

'''
    
    # Check if the validation code is already present
    content = ''.join(lines)
    if 'Check usage limits before processing' in content:
        print("✅ Usage validation code already present")
        return True
    
    # Insert the validation code
    lines.insert(target_line, validation_code)
    
    # Write back to file
    with open('silence_cutter.py', 'w', encoding='utf-8') as f:
        f.writelines(lines)
    
    print("✅ Successfully inserted usage validation code")
    print(f"📍 Code inserted at line {target_line + 1}")
    
    return True

if __name__ == "__main__":
    fix_usage_validation() 