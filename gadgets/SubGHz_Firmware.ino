#include <Arduino.h>
#include <Wire.h>
#include <SPI.h>
#include <RadioLib.h>
#include <Adafruit_GFX.h>
#include <Adafruit_SSD1306.h>

// ==========================================
// 1. DEFINICIÓN DE PINES
// ==========================================
// OLED (I2C)
#define OLED_SDA 4
#define OLED_SCL 5
#define SCREEN_WIDTH 128
#define SCREEN_HEIGHT 64

// Módulo 1: TX / Jammer (HSPI)
#define TX_CS    15
#define TX_GDO0  16
#define TX_SCK   14
#define TX_MISO  12
#define TX_MOSI  13

// Módulo 2: RX / Sniffer (VSPI)
#define RX_CS    21
#define RX_GDO0  22
#define RX_SCK   18
#define RX_MISO  19
#define RX_MOSI  23

// ==========================================
// 2. OBJETOS GLOBALES
// ==========================================
Adafruit_SSD1306 display(SCREEN_WIDTH, SCREEN_HEIGHT, &Wire, -1);

// Instancias de buses SPI
SPIClass spiTX(HSPI);
SPIClass spiRX(VSPI);

// Instancias de RadioLib para cada módulo
CC1101 radioTX = new Module(TX_CS, TX_GDO0, RADIOLIB_NC, RADIOLIB_NC, spiTX);
CC1101 radioRX = new Module(RX_CS, RX_GDO0, RADIOLIB_NC, RADIOLIB_NC, spiRX);

// Mutex para evitar que ambos núcleos escriban al Serial al mismo tiempo
SemaphoreHandle_t serialMutex;

// ==========================================
// 3. MÁQUINA DE ESTADOS Y VARIABLES
// ==========================================
enum SystemState { IDLE, SNIFFING_433, JAMMING_433, SENDING_PACKET, ROLLJAM_ACTIVE };
volatile SystemState currentState = IDLE;

// Variables de control de tiempo
volatile unsigned long jammerStartTime = 0;
volatile unsigned long jammerDuration = 0;

// Variable para el comando SEND (ya NO es volatile, se accede con sincronización por bandera)
String txDataHex = "";               
volatile bool sendRequested = false;

// Flag para interrupción de recepción
volatile bool packetReceived = false;

// ==========================================
// 4. FUNCIONES DE INTERRUPCIÓN (ISR)
// ==========================================
// Esta ISR se dispara cuando el Módulo 2 (RX) detecta un paquete
void IRAM_ATTR setFlagRX() {
  packetReceived = true;
}

// ==========================================
// 5. FUNCIONES AUXILIARES
// ==========================================
void updateOLED(String status, String details = "") {
  display.clearDisplay();
  display.setTextSize(1);
  display.setTextColor(SSD1306_WHITE);
  
  display.setCursor(0, 0);
  display.println("DragonFly RF Coproc");
  display.drawLine(0, 10, 128, 10, SSD1306_WHITE);
  
  display.setTextSize(2);
  display.setCursor(0, 18);
  display.println(status);
  
  if (details != "") {
    display.setTextSize(1);
    display.setCursor(0, 45);
    display.println(details);
  }
  
  display.display();
}

void safeSerialPrint(String msg) {
  if (xSemaphoreTake(serialMutex, portMAX_DELAY)) {
    Serial.println(msg);
    xSemaphoreGive(serialMutex);
  }
}

// ==========================================
// 6. TAREA CORE 0: COMUNICACIONES Y UI
// ==========================================
void TaskComms(void *pvParameters) {
  String inputBuffer = "";
  
  for (;;) {
    // 1. Leer comandos desde la Pi Zero
    if (Serial.available() > 0) {
      char c = Serial.read();
      if (c == '\n') {
        inputBuffer.trim();
        
        // Parseo del protocolo
        if (inputBuffer.startsWith("CMD:SNIFF:")) {
          currentState = SNIFFING_433;
          updateOLED("SNIFFING", "Freq: 433 MHz");
          safeSerialPrint("ACK:SNIFF_STARTED");
          
        } else if (inputBuffer.startsWith("CMD:JAM:")) {
          // Extraer duración (ej: CMD:JAM:433:10)
          int lastColon = inputBuffer.lastIndexOf(':');
          String durStr = inputBuffer.substring(lastColon + 1);
          jammerDuration = durStr.toInt() * 1000; 
          jammerStartTime = millis();
          
          currentState = JAMMING_433;
          updateOLED("JAMMING!", "Time: " + durStr + "s");
          safeSerialPrint("ACK:JAM_STARTED");
          
        } else if (inputBuffer.startsWith("CMD:SEND:")) {
          // Formato esperado: CMD:SEND:433:HEXDATA
          int thirdColon = inputBuffer.lastIndexOf(':');          // antes del hex
          int secondColon = inputBuffer.lastIndexOf(':', thirdColon - 1); // antes de la frecuencia
          if (secondColon != -1 && thirdColon != -1) {
            String hexPart = inputBuffer.substring(thirdColon + 1);
            hexPart.trim();
            if (hexPart.length() > 0) {
              txDataHex = hexPart;               // Core 0 escribe el dato
              sendRequested = true;              // Activa la bandera
              safeSerialPrint("ACK:SEND_QUEUED");
            } else {
              safeSerialPrint("ERR:SEND_EMPTY");
            }
          } else {
            safeSerialPrint("ERR:SEND_FORMAT");
          }
          
        } else if (inputBuffer.startsWith("CMD:ROLLJAM:START")) {
          currentState = ROLLJAM_ACTIVE;
          updateOLED("ROLLJAM", "RX & TX Active");
          safeSerialPrint("ACK:ROLLJAM_STARTED");
          
        } else if (inputBuffer.startsWith("CMD:STOP")) {
          currentState = IDLE;
          updateOLED("IDLE", "Ready.");
          safeSerialPrint("ACK:STOPPED");
        }
        
        inputBuffer = "";
      } else {
        inputBuffer += c;
      }
    }
    
    // Pequeño delay para no saturar el Watchdog del Core 0
    vTaskDelay(10 / portTICK_PERIOD_MS); 
  }
}

// ==========================================
// 7. TAREA CORE 1: RADIOFRECUENCIA (RF)
// ==========================================
void TaskRF(void *pvParameters) {
  SystemState lastState = IDLE;
  
  for (;;) {
    // Detectar cambios de estado para configurar los módulos
    if (currentState != lastState) {
      // Limpiar configuraciones anteriores
      radioTX.standby();
      radioRX.standby();
      packetReceived = false;
      
      switch (currentState) {
        case SNIFFING_433:
          // Configurar Modulo 2 para escuchar
          radioRX.setFrequency(433.92);
          radioRX.startReceive();
          break;
          
        case JAMMING_433:
          // Configurar Modulo 1 para transmitir ruido
          radioTX.setFrequency(433.92);
          // transmitDirect() emite una portadora continua (ruido) sin modular
          radioTX.transmitDirect(); 
          break;
          
        case SENDING_PACKET: {
          // Configurar el módulo TX en 433.92 MHz
          radioTX.setFrequency(433.92);
          // Convertir hex string a array de bytes
          int len = txDataHex.length() / 2;
          if (len > 0) {
            uint8_t* bytes = new uint8_t[len];
            for (int i = 0; i < len; i++) {
              bytes[i] = (uint8_t) strtol(txDataHex.substring(i*2, i*2+2).c_str(), NULL, 16);
            }
            // Transmisión bloqueante: envía la trama completa y retorna al terminar
            int state = radioTX.transmit(bytes, len);
            delete[] bytes;
            if (state == RADIOLIB_ERR_NONE) {
              safeSerialPrint("ACK:SEND_DONE");
            } else {
              safeSerialPrint("ERR:SEND_FAILED");
            }
          } else {
            safeSerialPrint("ERR:SEND_EMPTY_DATA");
          }
          txDataHex = "";      // Limpiar el buffer
          // Regresar inmediatamente a IDLE después del envío
          currentState = IDLE;
          updateOLED("IDLE", "TX Done.");
          break;
        }
          
        case ROLLJAM_ACTIVE:
          // Configurar ambos: Modulo 1 Jamea (offset sutil), Modulo 2 Escucha
          radioTX.setFrequency(433.92); 
          radioRX.setFrequency(433.92); 
          radioTX.transmitDirect(); // Empieza a hacer ruido
          radioRX.startReceive();   // Intenta escuchar a través del ruido
          break;
          
        case IDLE:
        default:
          break;
      }
      lastState = currentState;
    }
    
    // Lógica continua según el estado actual
    switch (currentState) {
      
      case SNIFFING_433:
      case ROLLJAM_ACTIVE:
        if (packetReceived) {
          packetReceived = false;
          String strData;
          int state = radioRX.readData(strData);
          
          if (state == RADIOLIB_ERR_NONE) {
            // Convertir la data capturada a HEX plano
            String hexString = "";
            for (int i = 0; i < strData.length(); i++) {
              if (strData[i] < 16) hexString += "0";
              hexString += String(strData[i], HEX);
            }
            hexString.toUpperCase();
            
            // Enviar a la Pi Zero
            safeSerialPrint("DATA:HEX:" + hexString);
          }
          // Reiniciar escucha
          radioRX.startReceive();
        }
        break;
        
      case JAMMING_433:
        // Controlar el temporizador del Jammer
        if (millis() - jammerStartTime >= jammerDuration) {
          currentState = IDLE;
          updateOLED("IDLE", "Jamming Done.");
          safeSerialPrint("ACK:JAM_STOPPED");
        }
        break;
        
      // El estado SENDING_PACKET ya no necesita manejo continuo;
      // la transmisión se completa en el bloque de cambio de estado.
        
      case IDLE:
        break;
    }
    
    // Comprobar si se solicitó un envío estando en IDLE
    if (sendRequested && currentState == IDLE) {
      sendRequested = false;
      currentState = SENDING_PACKET;
      lastState = IDLE;  // forzar la reconfiguración del módulo
    }
    
    // Delay muy corto en Core 1 para respuesta rápida a RF
    vTaskDelay(2 / portTICK_PERIOD_MS); 
  }
}

// ==========================================
// 8. SETUP PRINCIPAL
// ==========================================
void setup() {
  Serial.begin(115200);
  serialMutex = xSemaphoreCreateMutex();
  
  // 1. Iniciar OLED
  Wire.begin(OLED_SDA, OLED_SCL);
  if (!display.begin(SSD1306_SWITCHCAPVCC, 0x3C)) {
    safeSerialPrint("ERR:OLED_NOT_FOUND");
    while (true); // Detener si no hay pantalla (opcional)
  }
  updateOLED("BOOTING...", "Init Hardware");
  
  // 2. Iniciar Buses SPI
  spiTX.begin(TX_SCK, TX_MISO, TX_MOSI, TX_CS);
  spiRX.begin(RX_SCK, RX_MISO, RX_MOSI, RX_CS);
  
  // 3. Iniciar Módulo 1 (TX)
  int stateTX = radioTX.begin();
  if (stateTX != RADIOLIB_ERR_NONE) {
    safeSerialPrint("ERR:MODULE1_TX_FAILED");
    updateOLED("ERROR", "Mod 1 TX Fail");
    while (true);
  }
  
  // 4. Iniciar Módulo 2 (RX)
  int stateRX = radioRX.begin();
  if (stateRX != RADIOLIB_ERR_NONE) {
    safeSerialPrint("ERR:MODULE2_RX_FAILED");
    updateOLED("ERROR", "Mod 2 RX Fail");
    while (true);
  }
  
  // Asignar interrupción al Módulo RX (GDO0)
  radioRX.setGdo0Action(setFlagRX, RISING);
  
  updateOLED("IDLE", "Ready.");
  safeSerialPrint("ACK:BOOT_COMPLETE");

  // 5. Crear Tareas en los Núcleos correspondientes
  xTaskCreatePinnedToCore(
    TaskComms, "TaskComms", 4096, NULL, 1, NULL, 0
  );
  
  xTaskCreatePinnedToCore(
    TaskRF, "TaskRF", 8192, NULL, 2, NULL, 1
  );
}

void loop() {
  vTaskDelete(NULL); 
}
