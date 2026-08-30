import cv2
import numpy as np
import os

os.makedirs('tests/fixtures/real_world', exist_ok=True)

# 1. Low-quality black bottle image
# Small size, very dark, blurry
img_black = np.full((300, 300, 3), (20, 20, 20), dtype=np.uint8)
cv2.putText(img_black, 'NUTRITION FACTS', (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 0.5, (50, 50, 50), 1)
img_black = cv2.GaussianBlur(img_black, (15, 15), 0)
cv2.imwrite('tests/fixtures/real_world/low_quality_black_bottle.jpg', img_black)

# 2. Original real soda bottle (acceptable)
# 800x800, well lit (brightness ~120)
img_soda = np.full((800, 800, 3), (120, 120, 120), dtype=np.uint8)
cv2.putText(img_soda, 'MANUFACTURED BY SODA INC', (50, 200), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
# add a small specular highlight (glare) that is < 5% of the image
cv2.rectangle(img_soda, (100, 100), (150, 150), (255, 255, 255), -1) 
cv2.imwrite('tests/fixtures/real_world/real_soda_bottle.jpg', img_soda)

# 3. PureShield generated cleaner image
# Mostly white, sharp text
img_pure = np.full((1000, 1000, 3), (250, 250, 250), dtype=np.uint8)
cv2.putText(img_pure, 'PURESHIELD', (100, 100), cv2.FONT_HERSHEY_SIMPLEX, 2, (0, 0, 0), 3)
cv2.imwrite('tests/fixtures/real_world/pureshield_cleaner.jpg', img_pure)

print("Generated dummy images for testing.")
