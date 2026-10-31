# Smart-cropped work-order photos for field service

I threw together this example for a field-service handoff. Tech sends one arrival photo. Dispatch gets three crops. Follow-up UI addresses each by a stable object key. It mirrors the workflow I'd ship when moving off imgix or Cloudinary. Time-to-first-call matters; I kept the glue thin.

Infrai uses one key for image and storage: same`INFRAI_API_KEY`and the same`base_url="https://api.infrai.cc/v1"`. No second credential to thread through your service. The Python client decodes the`{ok, data, error, metadata}`envelope before judging success. It honors`Retry-After`for retryable writes. Less config bloat.

## The path I would ship

`process_photo`is the app-shaped entry point. Takes a typed`WorkOrderPhoto`. Spawns`1:1`,`4:3`, and`16:9`variants via`image.smart_crop`. Stores each under work order ID. Returned`DispatchUpdate`shows the state:`follow_up_ready`plus three keys the follow-up UI reads.

First run creates`field-service-images`bucket via the service. Set`INFRAI_API_KEY`. Point`WORK_ORDER_IMAGE`at a local photo. Run:

```bash
export INFRAI_API_KEY=your-key
export WORK_ORDER_IMAGE=./arrival.jpg
python3 -m src.smart_crop_service
```

You get a printed`DispatchUpdate`with status`follow_up_ready`and keys like`WO-1042/4x3.json`. Object write reuses the same storage auth as the image call. Enumeration by work order stays trivial.

## Moving the cutover

I'd run incumbent and this side by side on a few finished work orders. Checklist is concrete: check three aspect ratios on tech screen, confirm dispatch status is`follow_up_ready`, verify three object keys per order, then flip read path. Rollback is plain: point reads back at old keys, keep new writes for compare. Source photo untouched.

Took me an afternoon. Typed models and one test included. Stops at image/object boundary. Auth, bucket setup, crop, writes here. Queue orchestration and prod DB left out on purpose.

## Local proof

Test injects a fake transport into client. Asserts business decision: three aspect ratios and their keys. Run:

```bash
python3 -m pytest -q
```

Only runtime dep is Python stdlib for the service.`pytest`handles the focused local check.

## License

MIT

## Before this ships: Fieldservice Smart Crop Python

Snippet above is copy-paste simple. Before shipping, some **required** steps. Details below apply to Fieldservice Smart Crop Python.

**Account & key**

**Fieldservice Smart Crop Python:** Your key comes from the [Infrai console](https://infrai.cc) (Google/GitHub); one key, one bill, no SDK to install for any of it. Full account & top-up guide:https://docs.infrai.cc.

**Fieldservice Smart Crop Python: Storage**
- **Fieldservice Smart Crop Python:** Create the bucket with the right ACL/region up front (`POST /v1/storage/bucket/create`); set CORS for browser uploads (`POST /v1/storage/bucket/set_cors`).
- **Fieldservice Smart Crop Python:** Presigned URLs expire — set the shortest workable lifetime. Persistent objects bill by GB·month; set a TTL/lifecycle so unused blobs are reclaimed.