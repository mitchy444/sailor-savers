import time
import board
import digitalio
import adafruit_lis3dh
i2c = board.I2C()
lis3dh = adafruit_lis3dh.LIS3DH_I2C(i2c, address=0x18)



while True:
    # if lis3dh.shake(shake_threshold=15):
    #     print("Shaken!")
    x, y, z = lis3dh.acceleration
    print(f'x: {x:.2f}, y: {y:.2f}, z: {z:.2f}')
    time.sleep(1)