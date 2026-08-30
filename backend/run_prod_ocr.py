import cv2, sys, time
from app.services.ocr_engine import analyze_image

image = cv2.imread('tests/fixtures/real_world/coke_can.jpg')
start = time.time()
res = analyze_image(image)
t = time.time() - start
print(f'Execution time: {t:.2f}s')
for line in res:
    print(f'{line.text} | {line.confidence:.4f}')
