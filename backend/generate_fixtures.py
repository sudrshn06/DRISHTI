import os
import cv2
import numpy as np

os.makedirs('tests/fixtures', exist_ok=True)

# 1. Readable label
img = np.ones((200, 400, 3), dtype=np.uint8) * 255
cv2.putText(img, 'MRP Rs. 120', (10, 50), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
cv2.putText(img, 'Net Wt 500g', (10, 100), cv2.FONT_HERSHEY_SIMPLEX, 1, (0, 0, 0), 2)
cv2.imwrite('tests/fixtures/readable_test_label.jpg', img)

# 2. Blank image
blank_img = np.ones((100, 100, 3), dtype=np.uint8) * 255
cv2.imwrite('tests/fixtures/blank_image.jpg', blank_img)

# 3. Invalid file
with open('tests/fixtures/invalid_file.jpg', 'w') as f:
    f.write('This is not an image')
