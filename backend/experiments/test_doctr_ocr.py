import sys
import time
import argparse

def main():
    parser = argparse.ArgumentParser(description="Test docTR OCR configuration")
    parser.add_argument("image_path", help="Path to the image to test")
    args = parser.parse_args()

    print("Initializing docTR...")
    start_init = time.time()
    
    # Ensure it only uses CPU
    import os
    os.environ["USE_TORCH"] = "1"
    
    import doctr
    from doctr.io import DocumentFile
    from doctr.models import ocr_predictor

    # Pretrained OCR models
    predictor = ocr_predictor(det_arch="db_resnet50", reco_arch="crnn_vgg16_bn", pretrained=True)
    
    print(f"Initialization took {time.time() - start_init:.2f} seconds")
    
    print(f"\nProcessing image: {args.image_path}")
    doc = DocumentFile.from_images(args.image_path)
    
    start_process = time.time()
    result = predictor(doc)
    process_time = time.time() - start_process
    print(f"Execution took {process_time:.2f} seconds")
    
    print("\n--- RESULTS ---")
    print(f"{'TEXT':<50} | CONFIDENCE")
    print("-" * 65)
    
    word_count = 0
    line_count = 0
    
    for page in result.pages:
        for block in page.blocks:
            for line in block.lines:
                line_count += 1
                words = []
                confs = []
                for word in line.words:
                    word_count += 1
                    words.append(word.value)
                    confs.append(word.confidence)
                
                line_text = " ".join(words)
                line_conf = sum(confs)/len(confs) if confs else 0.0
                print(f"{line_text:<50} | {line_conf:.4f}")

    print("\n--- CONFIGURATION REPORT ---")
    print(f"docTR Version: {doctr.__version__}")
    # Try to grab the class name of the underlying models
    try:
        det_arch = predictor.det_predictor.model.__class__.__name__
    except:
        det_arch = "Unknown"
        
    try:
        rec_arch = predictor.rec_predictor.model.__class__.__name__
    except:
        rec_arch = "Unknown"
        
    print(f"Detection Architecture: {det_arch}")
    print(f"Recognition Architecture: {rec_arch}")
    print("Device: CPU")
    print(f"Execution Time: {process_time:.2f}s")
    print(f"Detected lines: {line_count}")
    print(f"Detected words: {word_count}")


if __name__ == "__main__":
    main()
