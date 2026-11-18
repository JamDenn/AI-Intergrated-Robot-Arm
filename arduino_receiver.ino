#include <ArduinoJson.h>
#include <Servo.h>

Servo gripperServo; // Servo for the gripper

void setup() {
    Serial.begin(9600);
    gripperServo.attach(12); // Change to the pin connected to your gripper servo
    Serial.print("Arduino is ready to receive commands.");
}
