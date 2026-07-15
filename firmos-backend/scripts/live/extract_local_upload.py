import sys, asyncio, io
sys.path.insert(0, '.')
from PIL import Image
from extraction.sarvam import _run_sarvam_pipeline

async def main():
    # Read the user's uploaded invoice (it's a WebP file)
    with open("uploads/doc-33e143e5.image", "rb") as f:
        raw_bytes = f.read()
    
    # Convert WebP to JPEG (same as the upload route does)
    img = Image.open(io.BytesIO(raw_bytes))
    if img.mode in ("RGBA", "P"):
        img = img.convert("RGB")
    out = io.BytesIO()
    img.save(out, format="JPEG", quality=95)
    jpeg_bytes = out.getvalue()
    
    print(f"Original size: {len(raw_bytes)} bytes, JPEG size: {len(jpeg_bytes)} bytes")
    print(f"Image dimensions: {img.size}")
    
    result = await _run_sarvam_pipeline(jpeg_bytes, "image/jpeg")
    print("Extraction completed; inspect the private run record in firmOS for reviewed results.")

asyncio.run(main())
