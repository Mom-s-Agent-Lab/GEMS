# Qwen-Image-2512 Configuration

Alibaba's #1-ranked open-source T2I model. Uses standard ComfyUI nodes with
FP8 quantized weights (~28 GB total, fits in 45 GB VRAM).

## Node graph

```
UNETLoader -> LoraLoaderModelOnly (optional) -> ModelSamplingAuraFlow -> KSampler
CLIPLoader -> CLIPTextEncode (positive) -> KSampler
CLIPLoader -> CLIPTextEncode (negative) -> KSampler
EmptySD3LatentImage -> KSampler
VAELoader -> VAEDecode
KSampler -> VAEDecode -> SaveImage
```

## KSampler settings

### Lightning mode (4 steps, with LoRA)
steps=4, cfg=1.0, sampler=`euler`, scheduler=`simple`, denoise=1.0

### Standard mode (50 steps, no LoRA)
steps=50, cfg=4.0, sampler=`euler`, scheduler=`simple`, denoise=1.0

## ModelSamplingAuraFlow
shift=3.1 (range 1.0-5.0). Higher = more structured. Required node.

## Resolution buckets

| Aspect | Width | Height |
|---|---|---|
| 1:1 | 1328 | 1328 |
| 16:9 | 1664 | 928 |
| 9:16 | 928 | 1664 |
| 4:3 | 1472 | 1104 |
| 3:4 | 1104 | 1472 |

## Prompt style

Use detailed sentences, not keyword lists. Qwen does NOT need quality
tokens like "masterpiece" or "8k uhd".

Negative prompt (Chinese preferred):
`低分辨率，低画质，肢体畸形，手指畸形，画面过饱和，蜡像感，人脸无细节，过度光滑，画面具有AI感`
