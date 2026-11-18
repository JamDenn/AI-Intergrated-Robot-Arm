import json
import serial
import os
import time
from google import genai
from google.genai import types
from google.genai.errors import ServerError

#Client Initialize
client = genai.Client(
    http_options = types.HttpOptions(timeout = 20000)
)

Initialize = input("Do you want to initialize the client? (Y/N): ")

#Operating Conditions
Envlope_Units = "mm"
Max_Envelope_Reach_mm = 500
Max_Payload_kg = 0.05
Golf_Ball_Diameter_mm = 42.7


#Golf_Tee_Position_mm = __ ## Might be needed later
#Golf_Ball_Pickup_Position_mm = __ ## Might be needed later
Workspace_X_Limits_mm = (-200, 200)
Workspace_Y_Limits_mm = (100, 300)
Workspace_Z_Limits_mm = (0, 150)

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600

taught_sequence = []

def validate_coordinates(target):
    #Validates that target [x, y, z] coordinates fall within safe boundaries.
    x, y, z = target
    return (Workspace_X_Limits_mm[0] <= x <= Workspace_X_Limits_mm[1] and
            Workspace_Y_Limits_mm[0] <= y <= Workspace_Y_Limits_mm[1] and 
            Workspace_Z_Limits_mm[0] <= z <= Workspace_Z_Limits_mm[1])

def send_to_hardware(command_data):
    #Sends JSON command payload over serial to the microcontroller.
    try:
        with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
            time.sleep(2) # Wait for the Arduino to reset
            payload = json.dumps(command_data) + "\n"
            ser.write(payload.encode('utf-8'))
            print(f"Sent command to robot: {payload.strip()}")
    except serial.SerialException as e:
        print(f"Serial communication error: {e}")

def AI_task_mode():
    #Queries Gemini for high-level task planning and coordinate generation.
    #Client Setup
    system_prompt = (
        "You are the advanced control brain for a Lynxmotion AL5D robot arm configured as a Golf Ball Teeing Robot. "
        f"All Cartesian coordinates (X, Y, Z) must be provided in {Envlope_Units} (millimeters) relative to the robot base center.  "
        f"The coordinated workspace is limited to X: {Workspace_X_Limits_mm}, Y: {Workspace_Y_Limits_mm}, Z: {Workspace_Z_Limits_mm}. "
        f"The golf ball has a diameter of {Golf_Ball_Diameter_mm} mm. "
        "Your task is to manage a two-stage sequential operation when requested: "
        "Stage 1: 'move_to_ball' (approach and pick up the golf ball using the cup gripper, gripper: 'closed'). "
        "Stage 2: 'place_on_tee' (move to and place the ball precisely onto the golf tee, gripper: 'open'). "
        "Respond ONLY with a JSON object containing the action, target coordinates where z_mm is the vertical position, and gripper state in this exact format: "
        '{"action": "move_to_ball" | "place_on_tee", "target": [x_mm, y_mm, z_mm], "gripper": "open" | "closed"}'
    )

    workflow_steps = [
    "Step 1: Move to the left pickup zone at [-150, 180, 21.4], approach the golf ball, and close the gripper.",
    "Step 2: Move to the golf tee located at [0, 220, 35], place the golf ball, and open the gripper to release it."
    ]   

    # user_command = input("Enter your command: ")
    # print(f"Sending user command: {user_command}")

    #Client Initialization and Command Processing
    max_retries = 3
    try:
        for step_num, current_step_prompt in enumerate(workflow_steps, start=1):
            print(f"\n---EXECUTING STEP {step_num}: {current_step_prompt}---")

            for attempt in range(max_retries):
                try:
                    print(f"Attempt no. {attempt + 1} of {max_retries} to connect to the server.")
                    robot_response = client.models.generate_content(
                        model = "gemini-3.6-flash",
                        contents = current_step_prompt,
                        config = types.GenerateContentConfig(
                            system_instruction = system_prompt,
                        )
                    )
                    break
                except ServerError:
                    if attempt < max_retries - 1:
                        print(f"Servers busy(503). Retrying in {2 ** attempt} seconds.")
                        time.sleep(2 ** attempt)
                    else:
                        raise

            ai_output = robot_response.text.strip()
            print("Raw ai_output:", ai_output)

            if ai_output.startswith("```json"):
                ai_output = ai_output[7:-3].strip()
            elif ai_output.startswith("```"):
                ai_output = ai_output[3:-3].strip()

            try:            
                command_data = json.loads(ai_output)
                print("Parsed command data:", command_data)
                if validate_coordinates(command_data["target"]):
                    send_to_hardware(command_data)
                else:
                    print(f"Error: Target coordinates {command_data['target']} are out of workspace limits.")
            except json.JSONDecodeError:
                print("Error: Failed to parse AI output as JSON. Raw output:", ai_output)
    except ServerError:
        raise
    except Exception as e:
        print(f"An error occurred: {e}")

def teach_mode_add_waypoint():
    #Allows a non-specialist operator to record a custom spatial waypoint.
    print("\n---Teach Mode: Add Waypoint---")
    try:
        x=float(input(f"Enter X coordinate in {Envlope_Units}: "))
        y=float(input(f"Enter Y coordinate in {Envlope_Units}: "))
        z=float(input(f"Enter Z coordinate in {Envlope_Units}: "))

        gripper_state = input("Enter gripper state ('open' or 'closed'): ").strip().lower()

        target = [x, y, z]
        if not validate_coordinates(target):
            print("Target coordinates are out of workspace limits. Please try again.")
            return

        step = {
            "action": "teach_move",
            "target": target,
            "gripper": gripper_state if gripper_state in ["open", "closed"] else "open"
        }
        taught_sequence.append(step)
        print(f"Waypoint {len(taught_sequence)} added: {step}")
    except ValueError:
        print("Invalid input. Please enter numeric values for coordinates.")

def view_taught_routine():
    #Displays all currently saved waypoints in the sequence.
    print(f"\n--- Taught Routine ({len(taught_sequence)} steps) ---")
    if not taught_sequence:
        print("No waypoints recorded yet.")
    for idx, step in enumerate(taught_sequence, start=1):
        print(f"Step {idx}: {step}")

def replay_taught_routine():
    #Executes the recorded sequence of waypoints autonomously.
    print(f"\n--- Replaying Taught Routine ({len(taught_sequence)} steps) ---")
    if not taught_sequence:
        print("No routine recorded. Please use teach mode to add waypoints first.")
        return
    for idx, step in enumerate(taught_sequence, start=1):
        print(f"Executing Step {idx}: {step}")
        send_to_hardware(step)
        time.sleep(1)  # Optional delay between steps

  
def main(): 
    while True:
        print("\n=== Lynxmotion AL5D Control & Teach Mode Console ===")
        print("1. AI Task Prompt (Gemini)")
        print("2. Teach Mode: Add Waypoint")
        print("3. View Taught Routine")
        print("4. Replay Taught Routine")
        print("5. Exit")

        choice = input("Select an option (1-5): ")
        
        if choice == '1':
            AI_task_mode()
        elif choice == '2':
            teach_mode_add_waypoint()
        elif choice == '3':
            view_taught_routine()
        elif choice == '4':
            replay_taught_routine()
        elif choice == '5':
            print("Exiting program.")
            break
        else:
            print("Invalid choice. Please select a valid option.")

if Initialize.lower() == 'y':
    main()
else:
    print("Client initialization skipped. Exiting program.")
    quit()
