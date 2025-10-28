# Commands Specification

## Command Structure

| NAME | SIZE | DESC                                |
|:-----|-----:|:------------------------------------|
| LEN  | 2    | Total command size in little encian |
| CMD  | 2    | Command in little endian            |
| DAT  | -    | Data for command                    |

Request to `handle: 0x0006, uuid: 0000fa02-0000-1000-8000-00805f9b34fb`<br>
Responce from `handle: 0x0009, uuid: 0000fa03-0000-1000-8000-00805f9b34fb`<br>
(Need write 0x0100 to `handle: 0x000a, uuid: 00002902-0000-1000-8000-00805f9b34fb`)

## Initializing Sequence

 - get_device_info
 - get_cur_time
 - verify_pwd

## Send Image Sequence

- set_prg_mode
- send_png_data or send_gif_data or send_mix_data or set_text

## Send Temporary Image Sequence

- set_diy_mode
- send_png_data or send_gif_data or send_mix_data or set_text to 0x65

## 0x0002 - send_png_data

**Request**<br>
CMD: 0x0002<br>
DAT:

| NAME         | SIZE | DESC                  |
|:-------------|-----:|:----------------------|
| UNKNOWN      | 1    | 0x00 fixed            |
| PNG_SIZE_LE  | 4    | PNG data size         |
| PNG_CRC32_LE | 4    | CRC32 of PNG data     |
| UNKNOWN      | 1    | 0x00 fixed            |
| SCR_NO       | 1    | 0x01 - 0xFF (1 - 255) |
| PNG_RAW_DATA | X    | PNG raw data          |

SCR_NO<br>
 01 - 64: PRG<br>
      65: DIY<br>
 6F - 77: Remocon 1 - 9

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC             |
|:-----|-----:|:-----------------|
| RET  | 1    | NG:other OK:0x03 |

**Note**<br>
Show automatically when sent complete

## 0x0003 - send_gif_data

**Request**<br>
CMD: 0x0003<br>
DAT:

| NAME         | SIZE | DESC                  |
|:-------------|-----:|:----------------------|
| UNKNOWN      | 1    | 0x00 fixed            |
| GIF_SIZE_LE  | 4    | GIF data size         |
| GIF_CRC32_LE | 4    | CRC32 of GIF data     |
| UNKNOWN      | 1    | 0x00 fixed            |
| SCR_NO       | 1    | 0x01 - 0xFF (1 - 255) |
| GIF_RAW_DATA | X    | GIF raw data          |

SCR_NO<br>
 01 - 64: PRG<br>
      65: DIY<br>
 6F - 77: Remocon 1 - 9

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC             |
|:-----|-----:|:-----------------|
| RET  | 1    | NG:other OK:0x03 |

**Note**<br>
Show automatically when sent complete

## 0x0004 - send_mix_data

**Request**<br>
CMD: 0x0004<br>
DAT:

| NAME         | SIZE | DESC                  |
|:-------------|-----:|:----------------------|
| UNKNOWN      | 1    | 0x00 fixed            |
| DAT_SIZE_LE  | 4    | DAT data size         |
| DAT_CRC32_LE | 4    | CRC32 of DAT data     |
| UNKNOWN      | 1    | 0x02 fixed            |
| SCR_NO       | 1    | 0x01 - 0xFF (1 - 255) |
| MIX_DATA     | X    | Mixed data            |

MIX_DATA can container PNG GIF TEXT<br>
Block Header is unknown

PART_TYPE=TXT1,TXT2
```
TXT1: 8000 0000 0300 0060 1000 6400 0064 0000
TXT2: 8000 0000 0300 1060 1000 6400 0064 0000
```

PART_TYPE=GIF1,TXT1
```
GIF1: 610F 0000 0100 0020 2000 0000 0064 0000
TXT1: 8000 0000 0320 0040 2000 6400 0064 0000
```

PART_TYPE=TXT1,GIF1
```
TXT1: 8000 0000 0300 0040 2000 6400 0064 0000
GIF1: 610F 0000 0140 0020 2000 0000 0064 0000
```

PART_TYPE=GIF1,TXT1,TXT2
```
GIF1: 610F 0000 0100 0020 2000 0000 0064 0000
TXT1: 8000 0000 0320 0040 1000 6400 0064 0000
TXT2: 8000 0000 0320 1040 1000 6400 0064 0000
```

PART_TYPE=TXT1,TXT2,GIF1
```
TXT1: 8000 0000 0300 0040 1000 6400 0064 0000
TXT2: 8000 0000 0300 1040 1000 6400 0064 0000
GIF1: 610F 0000 0140 0020 2000 0000 0064 0000
```

other, jpg, png.....

**Note**<br>
Show automatically when sent complete

## 0x0100 - set_text:

**Request**<br>
CMD: 0x0100<br>
DAT:

| NAME         | SIZE | DESC                                   |
|:-------------|-----:|:---------------------------------------|
| UNKNOWN      | 1    | 0x00 fixed                             |
| DAT_SIZE_LE  | 4    | DAT data size                          |
| DAT_CRC32_LE | 4    | CRC32 of DAT data                      |
| UNKNOWN      | 1    | 0x00 fixed                             |
| SCR_NO       | 1    | 0x01 - 0xFF (1 - 255)                  |
| TXT_DATA     | X    | Text Data                              |

TXT_DATA:

| NAME         | SIZE | DESC                                   |
|:-------------|-----:|:---------------------------------------|
| DAT_LEN_LEN  | 2    | Text Length (< 0x1F4 (500))            |
| UNKNOWN      | 2    | 0x0101 fixed                           |
| EFFECT       | 1    | Fixed:0x00 RTL:0x01                    |
|              |      | LTR:0x02 Blink:0x05                    |
|              |      | Breeze:0x06 Snow:0x07                  |
|              |      | Laser:0x08                             |
| SPEED        | 1    | 0x01 - 0x64 (1 - 100)                  |
| STYLE        | 1    | 0x01:Fixed 0x02 - 0x09:?               |
| COLOR_FG ?   | 3    | RRGGBB                                 |
| UNKNOWN      | 1    | 0x01 fixed, text direction?            |
| COLOR_BG ?   | 3    | RRGGBB                                 |
| MIX_DATA     | X    | MIX_DATA can contain PIX and JPG data. |

PIX_DATA:

| NAME           | SIZE | DESC                                   |
|:---------------|-----:|:---------------------------------------|
| UNKNOWN        | 1    | 0x80 fixed                             |
| COLOR          | 3    | RRGGBB                                 |
| CHAR_SIZE      | 2    | 0x0A10:10x16 0x1420:20x32              |
| LINE_1_DATA_LE | 2    | 0b0:OFF 0x1:ON Right justified         |
| LINE_2_DATA_LE | 2    | ditt                                   |
| LINE_N_DATA_LE | 2    | ditt                                   |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC             |
|:-----|-----:|:-----------------|
| RET  | 1    | NG:other OK:0x03 |

## 0x0102 - delete_image

**Request**<br>
CMD: 0x0102<br>
DAT:

| NAME    | SIZE | DESC                  |
|:--------|-----:|:----------------------|
| NUM     | 2    | OFF:0x00 ON:0x01      |
| SCR_NO1 | 1    | 0x01 - 0xFF (1 - 255) |
| SCR_NO2 | 1    | 0x01 - 0xFF (1 - 255) |
| SCR_NON | 1    | 0x01 - 0xFF (1 - 255) |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x0104 - set_diy_mode: Switch DIY mode

**Request**<br>
CMD: 0x0104<br>
DAT:

| NAME | SIZE | DESC             |
|:-----|-----:|:-----------------|
| SW   | 1    | OFF:0x00 ON:0x01 |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x0105 - set_pixel: Set pixel in DIY mode

**Request**<br>
CMD: 0x0105<br>
DAT:

| NAME  | SIZE | DESC       |
|:------|-----:|:-----------|
| COLOR | 4    | 00RRGGBB   |
| POS_X | 1    | X position |
| POS_Y | 1    | Y position |

**Response**<br>
None

**Note**<br>
Send 3 times

## 0x0106 - set_clocke_mode: Switch CLOCK mode

**Request**<br>
CMD: 0x0106<br>
DAT:

| NAME      | SIZE | DESC                    |
|:----------|-----:|:------------------------|
| STYLE     | 1    | 0x01 - 0x08 (1 - 8)     |
| FMT_24H   | 1    | OFF:0x00 ON:0x01        |
| SHOW_DATE | 1    | OFF:0x00 ON:0x01        |
| YEAR      | 1    | 0x00 - 0x63 (00 - 99)   |
| MONTH     | 1    | 0x01 - 0x0C (01 - 12)   |
| DAY       | 1    | 0x01 - 0x1F (01 - 31)   |
| WEEK      | 1    | 0x01 - 0x07 (mon - sun) |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x0107 - set_pwr: Switch power

**Request**<br>
CMD: 0x0107<br>
DAT:

| NAME | SIZE | DESC             |
|:-----|-----:|:-----------------|
| SW   | 1    | OFF:0x00 ON:0x01 |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x0204 - set_pwd: Set the password

**Request**<br>
CMD: 0x0204<br>
DAT:

| NAME     | SIZE | DESC                         |
|:---------|-----:|:-----------------------------|
| PWD_SW   | 1    | OFF:0x00 ON:0x01             |
| PWD_1    | 1    | XX0000 of password (Not BCD) |
| PWD_2    | 1    | 00XX00 of password (Not BCD) |
| PWD_3    | 1    | 0000XX of password (Not BCD) |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x0205 - verify_pwd: Verify the password

**Request**<br>
CMD: 0x0205<br>
DAT:

| NAME  | SIZE | DESC                         |
|:------|-----:|:-----------------------------|
| PWD_1 | 1    | XX0000 of password (Not BCD) |
| PWD_2 | 1    | 00XX00 of password (Not BCD) |
| PWD_3 | 1    | 0000XX of password (Not BCD) |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x8001 - set_current_time: Set current time

**Request**<br>
CMD: 0x8001<br>
DAT:

| NAME      | SIZE | DESC                     |
|:----------|-----:|:-------------------------|
| HOUR      | 1    | 0x00 - 0x17 (00 - 23)    |
| MINUTE    | 1    | 0x00 - 0x3B (00 - 59)    |
| SECOND    | 1    | 0x00 - 0x3B (00 - 59)    |
| LANG      | 1    | NotChina:0x00 China:0x01 |

**Response**<br>
CMD: Same as request

| NAME      | SIZE | DESC                      |
|:----------|-----:|:--------------------------|
| LED_TYPE  | 1    | LED type                  |
| MINUTE    | 1    | 0x00 - 0x3B (00 - 59)     |
| SECOND    | 1    | 0x00 - 0x3B (00 - 59)     |
| LANG      | 1    | Not China:0x00 China:0x01 |
| HOUR      | 1    | 0x00 - 0x17 (00 - 23)     |
| LED_SW    | 1    | LED Power Flag            |
| PWD_SW    | 1    | Password Enable Flag      |

**Note**<br>
It will automatically power on

## 0x8002 - get_last_space: ???

**Request**<br>
CMD: 0x8002

**Response**<br>
None

## 0x8003 - set_default_mode: Reset to default mode

**Request**<br>
CMD: 0x8003

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x8004 - set_brightness: Set LED brightness

**Request**<br>
CMD: 0x8004<br>
DAT:

| NAME       | SIZE | DESC                  |
|:-----------|-----:|:----------------------|
| BRIGHTNESS | 1    | 0x01 - 0x64 (1 - 100) |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x8005 - get_device_info: Get device information

**Request**<br>
CMD: 0x8005

**Response**<br>
CMD: Same as request

| NAME       | SIZE | DESC                  |
|:-----------|-----:|:----------------------|
| MCU_FW_VER | 2    | MCU F/W Version XX.YY |
| BLE_FW_VER | 2    | BLE F/W Version XX.YY |

## 0x8006 - switch_upside_down: Switch upside down

**Request**<br>
CMD: 0x8006<br>
DAT:

| NAME | SIZE | DESC             |
|:-----|-----:|:-----------------|
| SW   | 1    | OFF:0x00 ON:0x01 |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |

## 0x8007 - switch_screen: Switch screen

**Request**<br>
CMD: 0x8007<br>
DAT:

| NAME | SIZE | DESC                |
|:-----|-----:|:--------------------|
| NUM  | 1    | 0x01 - 0x09 (1 - 9) |

**Response**<br>
None

## 0x8008 - set_prg_mode: Set slide view mode by specified screens

**Request**<br>
CMD: 0x8008<br>
DAT:

| NAME     | SIZE | DESC                  |
|:---------|-----:|:----------------------|
| NUM      | 2    | 0x01 - 0xFF (1 - 255) |
| SCR_NO_1 | 1    | 0x01 - 0xFF (1 - 255) |
| SCR_NO_2 | 1    | 0x01 - 0xFF (1 - 255) |
| SCR_NO_N | 1    | 0x01 - 0xFF (1 - 255) |

**Response**<br>
CMD: Same as request

| NAME | SIZE | DESC            |
|:-----|-----:|:----------------|
| RET  | 1    | NG:0x00 OK:0x01 |
