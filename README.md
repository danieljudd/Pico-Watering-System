# Pico-Watering-System
RP2040W Efficient Greenhouse Watering System

Why this exists:
University project AND, I really wanted something to measure my plant's health in the greenhouse because I'm usually busy.

- [Use case](#-use-case-(greenhouse))
- [Hardware parts](#-hardware-parts)
- [Configuration](#-configuration)
- [Images](#-images)


How it works + Features:

This system physically sits in a greenhouse and collects data locally on the Pico's 2MB of memory. It hosts a web service on a local network for accessible viewing of recently collected data and updates regularly. It can also run on batteries where 10k mAh = about 5 continuous days of runtime.

Optionally, this will actuate an attached relay to dispense water at a user-defined threshhold when soil becomes arid.

Grow lights can be attached which then turn on at dusk and watering actions will resume again in the morning.

Truncation of the file system can occur once the 2MB storage limit is approaching (fills in about a week), this will shift a batch of the newer data to the same, but vacated file. Allows system to run indefinitely (well, in testing it worked).

Wi-Fi reconnects every hour if connection is dropped, system will still run if this happens.

## Use case (Greenhouse):
- 24H statistical data collection and monitoring (easily import into spreadsheet for analysis)
- Remotely observe problems in temperature, humidity, number of daylight-hours.
- Good for a spotty Wi-Fi network connection
- Automated plant care while away on holiday, etc.
- Portable for smaller garden spaces
- Care for fussy plants or micro-manage lots of seeds
- More efficienct use of resources
- Reduce over or underwatering and potential reduction in soil bacterial/insect problems


## Hardware parts:
- Analogue light sensor (Any - with calibration)
- Analogue soil moisture sensor (Any - with calibration)
- Digital temperature and humidity sensor (DHT11)
- A case with side-gaps for sensors to sense but minimal moisture ingress
- Relay (3.3V actuation) - 2-Channel was used but any number is fine
    -    Water Pump (usually 12V)
    -    Fan (Need big enough one for measurable airflow)
    -    Lights (Use correct spectrum for growing)
- (Optional) Battery x2 - Battery pack to power relays and one USB connection for RP2040

## Configuration:
- Use Updated MicroPython firmware on RP2040 W
- Use Thonny:
    - Set Wi-Fi credentials
    - Set GPIO pins
    - Comment in/out routines that are not applicable
- Thonny console will show IP address on connection, or check your router


## Images:
- [UI main](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/1.jpg)
- [Recent data](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/2.jpg)
- [Watering in action](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/3.jpg)
- [Graph of compiled data from file system](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/4.jpg)
- [LED Light system](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/5.jpg)
- [Notifications area](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/6.jpg)
- [Wire/GPIO setup](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/7.jpg)
- [Box gap with external light sensor and soil moisture sensor](https://github.com/danieljudd/Pico-Watering-System/blob/main/Images/8.jpg)