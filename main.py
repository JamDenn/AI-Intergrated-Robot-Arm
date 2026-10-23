import json
#import serial
import os
import time
from google import genai
from google.genai import types
from google.genai.errors import ServerError

#Client Initialize
client = genai.Client(
    http_options = types.HttpOptions(timeout = 20000)
)

Initialize = input("Do you want to initialize the client? (Y/N): ") #Will be used to choose teach mode or run mode.

#Operating Conditions
Envlope_Units = "mm"
Max_Envelope_Reach_mm = 500
Max_Payload_kg = 0.05
Golf_Ball_Diameter_mm = 42.7

Workspace_X_Limits_mm = (-200, 200)
Workspace_Y_Limits_mm = (100, 300)
Workspace_Z_Limits_mm = (0, 150)

#Client Setup
system_prompt = (
"You are the advanced control brain for a Lynxmotion AL5D robot arm configured as a Golf Ball Teeing Robot. "
    f"All Cartesian coordinates (X, Y, Z) must be provided in {Envlope_Units} (millimeters) relative to the robot base center. "
    f"The golf ball has a diameter of {Golf_Ball_Diameter_mm} mm. "
    "Your task is to manage a two-stage sequential operation when requested: "
    "Stage 1: 'move_to_ball' (approach and pick up the golf ball using the cup gripper, gripper: 'closed'). "
    "Stage 2: 'place_on_tee' (move to and place the ball precisely onto the golf tee, gripper: 'open'). "
    "Respond ONLY with a JSON object containing the action, target coordinates where z_mm is the vertical position, and gripper state in this exact format: "
    '{"action": "move_to_ball" | "place_on_tee", "target": [x_mm, y_mm, z_mm], "gripper": "open" | "closed"}'
)

workflow_steps = [
    "Pick up the golf ball from the left pick up zone",
    "Place the golf ball on the tee."
]

# user_command = input("Enter your command: ")
# print(f"Sending user command: {user_command}")

SERIAL_PORT = "/dev/ttyUSB0"
BAUD_RATE = 9600

#Client Initialization and Command Processing
if Initialize.upper() == "Y":
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

            try:
                if ai_output.startswith("```json"):
                    ai_output = ai_output[7:-3].strip()
                elif ai_output.startswith("```"):
                    ai_output = ai_output[3:-3].strip()
                command_data = json.loads(ai_output)
                print(f"Succesful parsed data: (Units: {Envlope_Units})", command_data)

                #Validates the command data
                target_x, target_y, target_z = command_data["target"]
                if not (Workspace_X_Limits_mm[0] <= target_x <= Workspace_X_Limits_mm[1] and
                        Workspace_Y_Limits_mm[0] <= target_y <= Workspace_Y_Limits_mm[1] and
                        Workspace_Z_Limits_mm[0] <= target_z <= Workspace_Z_Limits_mm[1]):
                    print(f"Error: Target coordinates {command_data['target']} are out of workspace limits.")
                else:
                    print("Coordinates verified within safe workspace limits.")

                    # try:
                    #     with serial.Serial(SERIAL_PORT, BAUD_RATE, timeout=1) as ser:
                    #         payload = json.dumps(command_data) + "\n"
                    #         ser.write(payload.encode('utf-8'))
                    #         print(f"Sent command to robot: {payload.strip()}")
                    # except serial.SerialException as e:
                    #     print(f"Serial communication error: {e}")

            except json.JSONDecodeError as e:
                print("Failed to parse JSON:", e)
                break
    except ServerError:
        raise
    except Exception as e:
        print(f"An error occurred: {e}")
else:
    print("Client initialization skipped.")
