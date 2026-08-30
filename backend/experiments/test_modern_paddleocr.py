import sys
import time
import argparse
import logging

def main():
    parser = argparse.ArgumentParser(description="Test modern PaddleOCR 3.x API configuration")
    parser.add_argument("image_path", help="Path to the image to test")
    args = parser.parse_args()

    # Disable MKLDNN globally as required in some environments
    import os
    os.environ["FLAGS_use_mkldnn"] = "0"
    
    from paddleocr import PaddleOCR

    print("Initializing modern PaddleOCR 3.x configuration...")
    start_init = time.time()
    
    # Modern PaddleOCR configuration based on latest 3.x options
    ocr_model = PaddleOCR(
        lang="en",
        device="cpu", # Force CPU for benchmark consistency
        use_textline_orientation=True, # Modern replacement for use_angle_cls
        use_doc_orientation_classify=True,
        use_doc_unwarping=True,
        enable_mkldnn=False # Explicitly disabled
    )
    
    print(f"Initialization took {time.time() - start_init:.2f} seconds")
    
    print(f"\nProcessing image: {args.image_path}")
    start_process = time.time()
    
    # Modern predict API instead of deprecated ocr()
    result = ocr_model.predict(args.image_path)
    
    process_time = time.time() - start_process
    print(f"Execution took {process_time:.2f} seconds")
    
    print("\n--- RESULTS ---")
    print(f"{'TEXT':<50} | CONFIDENCE")
    print("-" * 65)
    
    if isinstance(result, list) and result:
        res_dict = result[0]
        if isinstance(res_dict, dict):
            texts = res_dict.get('rec_texts', [])
            scores = res_dict.get('rec_scores', [])
            for text, score in zip(texts, scores):
                print(f"{text:<50} | {score:.4f}")
        else:
            print("Unexpected result format:")
            print(res_dict)
    else:
         print("No text detected or unexpected result format.")

    import paddleocr
    print("\n--- CONFIGURATION REPORT ---")
    print(f"PaddleOCR Version: {paddleocr.__version__}")
    print("Recognition Model: default en")
    print("Detection Model: default")
    print("Enabled Options: use_textline_orientation, use_doc_orientation_classify, use_doc_unwarping")
    print("Device: CPU")
    print(f"Execution Time: {process_time:.2f}s")


if __name__ == "__main__":
    main()
