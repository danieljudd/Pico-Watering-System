# Made by Daniel Judd (Hosted at GitHub: danieljudd)
# Licences: https://github.com/danieljudd/Pico-Watering-System/blob/main/LICENSE

import network
import os
import socket
import time
import ntptime
import dht
import uasyncio as asyncio
from machine import Pin

# Set constants for GPIO or ADC pin connections
led = Pin("LED", Pin.OUT)
DHT11_Pin = 7
Soil_Pin = 27
Light_Pin = 28
Relay1 = Pin(0, Pin.OUT)
Relay2 = Pin(1, Pin.OUT)

## Turn relays and on-board LED OFF (if rebooting RPP)
led.value(0)
Relay1.value(1)
Relay2.value(1)

# User configuration
## low, medium, high = 5, 1, 0.5 minutes
LoggingRate = "high"
## Soil Aridity Limit (%)
WaterSoilAt = 40
## Engage Water Pump
WaterForSeconds = 1
## Engage Fan
SpinForSeconds = 120
## LED light duration
LightOnSeconds = 3600
## Notify when greenhouse temperatures reach:
TemperatureHigh = 37
TemperatureLow = 5
## Time between checking for problems (bad conditions)
PollingRate = 1800

## Network credentials
ssid = 'SSID'
password = 'SomePassword'

# Connect to WiFi using credentials
def connect():
    wifi = network.WLAN(network.STA_IF)
    wifi.active(True)
    # Power saving mode off
    wifi.config(pm = 0xa11140)
    wifi.connect(ssid, password)
    while wifi.isconnected() == False:
        print("Connecting...")
        time.sleep(1)
    print(wifi.ifconfig())

try:
    connect()
except KeyboardInterrupt:
    machine.reset()
# on-board RPP LED ON after network is connected
led.value(1)

# Set network time protocol host URL (external)
ntptime.host = "uk.pool.ntp.org"

# Network connection retrieves time from NTP host
# Must have network to configure
def SetTime():
    try:
        ntptime.settime()
        print("Time synced")
    except:
        print("Connecting to NTP...")
        time.sleep(1)
        SetTime()

SetTime()

# Extract data from Tuple and return String
## Output is always in UTC (add +1 for British Summer Time clock change)
## Expected format of outputs: 13/12/2023, 13:59:59
def GetDate():
    LocalDate = time.localtime()
    DateFormatted = ('{day}/{month}/{year}' .format(day=LocalDate[2], month=LocalDate[1], year=LocalDate[0]))
    return DateFormatted

def GetTime():
    LocalTime = time.localtime()
    TimeFormatted = ('{hour}:{minute}:{second}' .format(hour=LocalTime[3], minute=LocalTime[4], second=LocalTime[5]))
    return TimeFormatted

# Take constants configured by user and return analogue reading
## Range: (0-65535 or 2^16 bits)
def GetSensorData(PinNumber):
    try:
        aSensor = machine.ADC(PinNumber).read_u16()
        ## Make percentage of sensor range and round
        aSensor = round((aSensor/(2 ** 16 - 1)) * 100, 2)
        return str(aSensor)
    except Exception as e:
        print ("No reading from pin: " + PinNumber + (str(e)))

# Digital sensor reader "DHT11"
## Temperature and Humidity range and format: 0% to 100% (as String)
async def GetDHT():
    d = dht.DHT11(machine.Pin(DHT11_Pin))
    try:
        d.measure()
        temp = str(d.temperature())
        hum = str(d.humidity())
        x = hum, temp
        return x
    ## Specific DHT11 software crashes if read too frequently (e.g., <1s intervals)
    ## Will take error to console if debugging
    except Exception as e:
        await Notification(str(e))
        print ("No reading from DHT module")

# Assemble the sensor readings in a comma-separated string
async def Juncture():
    aDHT = await GetDHT()
    atime = GetTime()
    adate = GetDate()
    light = GetSensorData(Light_Pin)
    soil = GetSensorData(Soil_Pin)
    temperature = aDHT[1]
    humidity = aDHT[0]
    CombinedReadings = [atime,adate,soil,light,temperature,humidity]
    StringData = ','.join(CombinedReadings)
    return StringData


# Take in a data line to store, a max array size, and set pooled data in an existing global variable
def UpdateList(MyInput, MaxArray, StoreVar):
    Separate = SplitListByComma(MyInput)
    StoreVar.append(Separate)
    while (len(StoreVar) > MaxArray):
        StoreVar.pop(0)
    BuildList = []
    for entry in StoreVar:
        BuildList.append(entry)
    return BuildList

# Translate user configuration to useful machine interval
def LoggingFrequency():
    if LoggingRate == "high":
        return 30
    elif LoggingRate == "medium":
        return 60
    else:
        return 300

# (Test code for calculating memory use, requiring header: "import gc")
# "memory: " + str(gc.mem_free()) + " / " + str(gc.mem_alloc()

async def GetFileSize(file):
    FileSize = os.stat(file)
    # Calculate filesize in Kibibyte
    return (FileSize[6]/1024)

async def Truncate(file):
    # Free space in Kibibyte
    SystemSpace = (2048)
    # Reserve 10% of system space for system files
    FreeSpace = (SystemSpace - float(SystemSpace*0.1))
    if (await GetFileSize(file) > FreeSpace):
        try:
            with open(file, "r+") as f:
                
                # Find out lines in code
                TotalLines = (sum(1 for _ in f))
                f.seek(0)
                
                NumberOfKeptLines = 1000

                # Starting line position in file
                n = (TotalLines - NumberOfKeptLines)
                line_offset = []
                offset = 0
                for line in f:
                    line_offset.append(offset)
                    offset += len(line)
                f.seek(line_offset[n])
                
                LinesStored = ""
                for line in range(NumberOfKeptLines):
                    LinesStored = LinesStored + (next(f))
                    
            print("Truncating file from lines " + str(n) + " to " + str(n+NumberOfKeptLines))
                    
            # Open file as "w" automatically wiping file clean, apply new data
            with open(file, "w") as f:
                f.write(LinesStored)
        except Exception as e:
            await Notification(str(e))
            print("Error truncating file, " + str(e))

# Call to write to file every specified number of seconds
async def DataRegister(FileName, WriteMode, FrequencySeconds):
    ## Initialization as interface notification
    await Notification("Started sensor logging")
    
    ## Globals store values for all functions to access
    ### CSVArrangement = Basic string of sensor values (1 line)
    global CSVArrangement
    ### WebLayout = Store pre-compiled HTML parts with formatting, to lower overall latency
    global WebLayout
    ### StoredInstances = Append collected sensor values and truncate the oldest line to conserve system memory
    global StoredInstances
    StoredInstances = []
    
    while True:
        try:
            # Create file on system for permanent storage
            WriteCSV = open(FileName, WriteMode)
            
            ## Add arrangement of data to file
            CSVArrangement = await Juncture()
            WriteCSV.write(CSVArrangement)
            
            ## Create new line in CSV file for each new input
            WriteCSV.write("\n")
            print("logged")
            
            # Populate global variable with formatted data
            WebLayout = await ReformatWithHTML()
            
            ## Affix data to memory, delete oldest instance when MAX number of lines reached
            UpdateList(CSVArrangement, 20, StoredInstances)
            
            # Delete the OLD data in CSV file when capacity is critical, then "roll-over" most recent data
            await Truncate("logfile.csv")
            
            # Asynchronous sleep according to specified interval, let other tasks continue
            await asyncio.sleep(FrequencySeconds)
            
        # Have system errors (exceptions) show up in the debug console
        except Exception as e:
            # Write notification to file
            await Notification(str(e))
            print ("Logging stopped unexpectedly: " + str(e))
            break
        # Do these actions regardless
        finally:
            # Close file instance to conserve memory
            WriteCSV.close()

# Take values in String format and put back into list data structure
def SplitListByComma(aString):
    aList = aString
    # Erase new line and split into values on any comma (String to List)
    aList = aString.strip('\n').split(',')
    return aList

# Take global value "CSVArrangement" and format nicely for the main pages
async def ReformatWithHTML():
    MakeList = SplitListByComma(CSVArrangement)
    MakeList[0] = "<li> Time reported at: " + MakeList[0] + ' (UTC)</li>'
    MakeList[1] = "<li> Date reported at: " + MakeList[1] + ' (D/M/Y) </li>'
    MakeList[2] = "<li> Soil dryness: " + MakeList[2] + '%</li>'
    MakeList[3] = "<li> Light levels: " + MakeList[3] + '%</li>'
    MakeList[4] = "<li> Temperature: " + MakeList[4] + ' C</li>'
    MakeList[5] = "<li> Relative humidity: " + MakeList[5] + '%</li>'
    # Join the list as String-type HTML
    return (''.join(MakeList))

# Relay value "0" means ON, 1 is OFF, Relay
async def RelayControl(RelayName, delay):
    # Prevent relay being turned on successively
    if RelayName() == 0:
        print("already activated")
    else:
        RelayName.value(0)
        await asyncio.sleep(delay)
        message = ("Relay " + str(RelayName) + " was turned on for " + str(delay) + " seconds.")
        # Message is one line stored in CSV file
        # comma could create new columns
        message = message.replace(',', '')
        await Notification(message)
        RelayName.value(1)

# Store system events as notifications in memory as global variable
NotificationLogs = []


async def Notification(message):
    D = GetDate()
    T = GetTime()
    # Re-use "UpdateList" variable to structure log keeping with a line limit
    UpdateList(str(D + " " + T + " " + message), 10, NotificationLogs)
    # Put events here in named system file
    with open ("notifications.csv","a") as f:
        f.write(str(D + " " + T + " " + message))
        f.write("\n")

# Detect when to pause actuators in abscence of (day)light
async def WaitUntilDawn():
    while float(GetSensorData(Light_Pin)) < 5:
        print("Pausing actuators until dawn")
        # Interval to check for light
        await asyncio.sleep(600)
    # Close while loop and resume other tasks
    print("Dawn has been reached")

async def Actuator():
    while True:
        # Collect current integer values reported
        R = SplitListByComma(CSVArrangement)
        aTime = R[0]
        aDate = R[1]
        Soil = R[2]
        Light = R[3]
        Temp = R[4]
        Hum = R[5]
        
        try:
            # At night, only provide one interval of LED lighting
            if int(float(Light)) < 5:
                print("It's nighttime")
                ## Allow lights to turn on before pausing actuator functions
#                 await Notification("Lights engaged")
#                 await RelayControl(Relay1, int(LightOnSeconds))
#                 await Notification("Lights disengaged")
                await WaitUntilDawn()
            else:
                # Watering soil on Relay1
                if int(float(Soil)) > int(WaterSoilAt):
                    print ("Dry soil detected, watering")
                    await RelayControl(Relay1, WaterForSeconds)
                    
                # Fanning humidity on Relay2
                if int(float(Hum)) > 75:
                    print ("Humidity too high, fanning")
                    await RelayControl(Relay2, SpinForSeconds)
                elif int(float(Temp)) > 30:
                    print ("Temperature too high, fanning")
                    await RelayControl(Relay2, SpinForSeconds)
                
        finally:
            # Always check if temperature is high or low and report
            if int(float(Temp)) > TemperatureHigh:
                print ("Temperature too high, notifying")
                await Notification("Temperature too high: " + str(Temp) + "C")
            if int(float(Temp)) < TemperatureLow:
                print ("Temperature too low, notifying")
                await Notification("Temperature too low: " + str(Temp) + "C")
            # Checking interval
            await asyncio.sleep(PollingRate)

# Generate data for "uPlot" graphing software
def GraphData():
    # Copy variable containing data index (many CSV-type lines)
    GD = StoredInstances
    # group each sub-list (*) by the column groups and re-integrate 2D array (i.e., rotate)
    Rotate = [list(GD) for GD in zip(*GD)]
    
    # Generate ascending numbers on x-axis representing cycle
    AxisNumbers = []
    for n in range(1,21):
        AxisNumbers.append(n)
        
    NewFormat = []
    # add relevant grouped lists to graph (x-axis numbers, soil, light, temp, hum)
    NewFormat.insert(0,AxisNumbers)
    NewFormat.insert(1,Rotate[2])
    NewFormat.insert(2,Rotate[3])
    NewFormat.insert(3,Rotate[4])
    NewFormat.insert(4,Rotate[5])
    return NewFormat

# The BR tag forces a new line in HTML
def AddHtmlBr(feed):
    constructor = ""
    for item in feed:
        constructor = constructor + ', '.join(map(str, item)) + "<br>"
    return constructor

# Makes string adding list tags around a List objects in MicroPython
# Reasons for using this: https://developer.mozilla.org/en-US/docs/Web/HTML/Element/br#accessibility_concerns

def MakeHTMLList(feed):
    constructor = ""
    for item in feed:
        constructor = constructor + "<li>" + ', '.join(map(str, item)) + "</li>"
    return constructor

def MakeTableList(feed):
    constructor = ""
    for item in feed:
        constructor = constructor + "<tr>"
        for item in item:
            constructor = constructor + "<td>" + item + "</td>"
        constructor = constructor + "</tr>"
    return constructor

def TitleChanger(newtitle):
    UpdatedTitle = "<title>" + str(newtitle) + " - Efficient Greenhouse Plant Care system" "</title>"
    return UpdatedTitle

# Asynchronous web server to display sensor data
html = """<!DOCTYPE html>
<html lang="en">
    <head>
    {one}
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    {two}
    </head>
    <body>
        <h1>Efficient Greenhouse Plant Care system</h1>
        
        
        <ul role="menu">
        <li>
        <strong>
        Page Navigation:
        </strong>
        </li>
        <li>
        <a role="menuitem" href='/'>Go to Home Page</a>
        </li>
        <li>
        <a role="menuitem" href='/relay1/on'>Test Relay One</a>
        </li>
        <li>
        <a role="menuitem" href='/relay2/on'>Test Relay Two</a>
        </li>
        <li>
        <a role="menuitem" href='/logs/list'>List Recently Logged data</a>
        </li>
        <li>
        <a role="menuitem" href='/logs/monitor'>Check Notification Activity</a>
        </li>
        </ul>
        
        <br>
        
        <ul>
        <li>
        <strong>
        Sensor Data:
        </strong>
        </li>
        {three}
        </ul>
        
        <p>
        <strong>{four}</strong>
        </p>
        
        <div class="PlainData">
        {five}
        </div>
        
        {six}
        <br>
        
        
        
        <script>
        let data =
		{seven};
        </script>
        
        {eight}     
    </body>
</html>
"""

css = r"""
    <style>
    body {
        font-family: sans-serif;
        text-align: center;
    }
    
    ul {
    list-style-type: none;
    margin: 0;
    padding: 0;
    }
    
    li { 
        font-size: 1.2rem;
        list-style-type: none;
    }
    
    a:hover {
        background-color: blue;
        color: white;
    }
    
    a {
        text-decoration: none;
    }
    .PlainData * {
        border:1px solid grey;
    }
    table {
        margin-left: auto;
        margin-right: auto;
    }
    .uplot, .u-hz {
        display: inline-grid;
        justify-content: center;
    }
    </style>
"""

# Largely modified boilerplate code
# uPlot MIT License @ https://github.com/leeoniya/uPlot

graph = r"""<div class = "graph">
<link href="https://leeoniya.github.io/uPlot/dist/uPlot.min.css" rel="stylesheet">
<script src="https://leeoniya.github.io/uPlot/dist/uPlot.iife.min.js"></script>
		<script>

			function getSize() {
				return {
					width: window.innerWidth - 100,
					height: window.innerHeight - 200,
				}
			}

			const opts = {
				title: "Graph of measured data points:",
				...getSize(),
				 axes: [
                {
                  show: true,
                  label: "Cycle (rightmost newest)",
                },
                {
                  show: true,
                  label: "Magnitude",
                },
                ],
				scales: {
					x: {
						time: false,
						// snap x-zoom to exact data values
						range: (u, min, max) => [
							data[0][u.valToIdx(min)],
							data[0][u.valToIdx(max)],
						],
					},
				},
				hooks: {
					drawSeries: [
						(u, si) => {
							let ctx = u.ctx;

							ctx.save();

							let s  = u.series[si];
							let xd = u.data[0];
							let yd = u.data[si];

							let [i0, i1] = s.idxs;

							let x0 = u.valToPos(xd[i0], 'x', true);
							let y0 = u.valToPos(yd[i0], 'y', true);
							let x1 = u.valToPos(xd[i1], 'x', true);
							let y1 = u.valToPos(yd[i1], 'y', true);

							const offset = (s.width % 2) / 2;

							ctx.translate(offset, offset);

							ctx.beginPath();
							ctx.strokeStyle = s._stroke;
							ctx.setLineDash([5, 5]);
							ctx.moveTo(x0, y0);
							ctx.lineTo(x1, y1);
							ctx.stroke();

							ctx.translate(-offset, -offset);

							ctx.restore();
						}
					]
				},
				series: [
					{},
					{
						label: "Soil dryness (%)",
						stroke: "darkgreen",
					},
					{
						label: "Light levels (%)",
						stroke: "orange",
					},
					{
						label: "Temperature (C)",
						stroke: "darkred",
					},
					{
						label: "Relative humidity (%)",
						stroke: "darkblue",
					},
				],
			};
			
			
			
		let u = new uPlot(opts, data, document.body);

			function throttle(cb, limit) {
				var wait = false;

				return () => {
					if (!wait) {
						requestAnimationFrame(cb);
						wait = true;
						setTimeout(() => {
							wait = false;
						}, limit);
					}
				}
			}

		//	window.addEventListener("resize", throttle(() => u.setSize(getSize()), 100));
			window.addEventListener("resize", e => {
				u.setSize(getSize());
			});
		</script>
		</div>
"""

# end of uPlot code

async def serve_client(reader, writer):
    try:
        print("Client connected")
        request_line = await reader.readline()
        print("Request:", request_line)
        while await reader.readline() != b"\r\n":
            pass

        request = str(request_line)
        relay1 = request.find('/relay1/on')
        relay2 = request.find('/relay2/on')
        log_URL = request.find('/logs/list')
        monitor_URL = request.find('/logs/monitor')

        Title = "Home Page"
        StateIs = ""
        RequestLogs = ""
        RequestLogs2 = ""
        
        # Mainly test functions for relay setting "moulding"
        if relay1 == 6:
            print("relay1 on")
            StateIs = 'Turned on relay1'
            await RelayControl(Relay1, 1)
            print("relay1 off")
            Title = "Relay 1 has activated page"
            
        if relay2 == 6:
            print("relay2 on")
            StateIs = 'Turned on relay2'
            await RelayControl(Relay2, 1)
            print("relay2 off")
            Title = "Relay 2 has activated page"


        if log_URL == 6:
            print("requesting logs...")
            # Change [list] type to [string]
            StateIs = "<p>Recent sensor logs reported:</p>"
            RequestLogs = "<table><tr>" + "<th>Time (UTC)</th><th>Date</th><th>Soil dryness, %</th><th>Light levels, %</th><th>Temperature</th><th>Relative Humidity, %</th></tr>" + MakeTableList(StoredInstances) + "</table>"
            Title = "Logs in a table page"
            
        if monitor_URL == 6:
            StateIs = "Most recent notifications logged by date and time:"
            RefreshPage = """<script>setTimeout(() => {document.location.reload();},""" + str(LoggingFrequency()*1000) + """);</script>"""
            RequestLogs2 = MakeHTMLList(NotificationLogs) + RefreshPage
            Title = "Recent notifications of events page"

        # All data on web page is condensed here
        response = html .format(one=TitleChanger(Title), two=css, three=WebLayout, four=StateIs, five=RequestLogs, six=RequestLogs2, seven=GraphData(), eight=graph,)

        writer.write('HTTP/1.0 200 OK\r\nContent-type: text/html\r\n\r\n')
        writer.write(response)
        
        await writer.drain()
        await writer.wait_closed()

        print("Client disconnected")
    except Exception as e:
        await Notification(str(e))



async def main():
    print('Setting up webserver...')
    task1 = asyncio.create_task(asyncio.start_server(serve_client, "0.0.0.0", 80))
    # Network reconnect task:
    task2 = asyncio.create_task(connect2())
    # Asynchronous logging initiate (file, write type, interval seconds)
    task3 = asyncio.create_task(DataRegister("logfile.csv","a",LoggingFrequency()))
    # Routine relay checker and actuator
    task4 = asyncio.create_task(Actuator())
    
    await task1
    await task2
    await task3
    await task4
    

# fallback connect to network without interrupting other services
async def connect2():
    wifi = network.WLAN(network.STA_IF)
    while True:
        if wifi.isconnected() == False:
            print("Reconnecting to Wi-Fi")
            wifi.connect(ssid, password)
            await Notification("Network reconnected")
        await asyncio.sleep(600)

try:
    asyncio.run(main())
finally:
    asyncio.new_event_loop()
