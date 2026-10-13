# شرح PodSieve برای طراحی UI

این سند بر اساس run.py، configs/default.yaml و کد src تهیه شده است. برای این برنامه UI طراحی کن. گزینه‌های اصلی را در فرم هر مرحله و تنظیمات تخصصی را در بخش Advanced قرار بده. مقادیر پیش‌فرض را از YAML انتهای سند بگیر.

## مدل داده و وضعیت فعلی
- پروژه فعلاً CLI پایتون است؛ API وب، صف job و UI ندارد.
- هر speaker دارای چند source است. speaker_id باید speaker_ با ۳ تا ۶ رقم باشد؛ source_id باید source_ با ۳ تا ۶ رقم باشد.
- speaker_id نام مجموعه/هویت ثبت‌شده است؛ SPEAKER_00 و SPEAKER_01 برچسب‌های تشخیص مدل داخل هر source هستند. تطبیق خودکار هویت گوینده بین sourceها وجود ندارد.
- metadata.json وضعیت‌های pending و completed را ذخیره می‌کند. running/failed و درصد پیشرفت باید در لایهٔ job/UI اضافه شوند؛ log و exit code فعلی می‌توانند مبنای آن باشند.
- گزینهٔ overwrite پیش‌فرض false است و خروجی همان مرحله را جایگزین می‌کند. بازاجرای مرحلهٔ قبلی به معنی اجرای خودکار مراحل بعدی نیست.
- --config مسیر YAML و --data-root مسیر ذخیره‌سازی را در سطح کلی تعیین می‌کنند. پیش‌فرض configs/default.yaml و data است.

## ۱. دریافت ورودی / ingest
الزامی: speaker_id، source_id و دقیقاً یکی از دو ورودی زیر:
- مسیر فایل محلی: --input-file، مثل /home/user/podcast.mp3. فایل باید روی ماشین اجرای Python موجود باشد. کد فایل را با پسوند اصلی در raw کپی می‌کند. ingest فهرست محدود پسوند صوتی ندارد؛ تبدیل بعدی نیازمند فایل دارای stream صوتی قابل خواندن با FFmpeg است.
- URL: --url. فقط HTTP/HTTPS از YouTube یا Castbox پذیرفته می‌شود. سرویس از hostname تشخیص داده می‌شود؛ dropdown اجباری provider لازم نیست. دانلود playlist انجام نمی‌شود.
انتخاب فایل از سیستم/Upload در UI وب نیازمند پیاده‌سازی انتقال فایل به backend است؛ قابلیت فعلی مسیر محلی است.
اختیاری: --name (نام speaker، پیش‌فرض خالی)، --gender (متن آزاد، خالی)، --language (پیش‌فرض fa)، --overwrite (false).

برای URL، تنظیمات زیر در بخش Advanced دانلود قرار بگیرند:
- download.format: انتخاب stream در yt-dlp؛ پیش‌فرض 251/140/bestaudio.
- download.audio_format: فرمت فایل دانلودشده؛ پیش‌فرض opus.
- download.youtube_format و download.castbox_format: override اختیاری برای هر provider؛ در YAML فعلی نوشته نشده‌اند اما کد می‌خواند. اگر تعیین نشوند download.format اعمال می‌شود. fallback داخلی Castbox در نبود format برابر bestaudio/best است.
- روش کوکی YouTube: بدون کوکی / از مرورگر / از فایل کوکی.
- download.cookies_from_browser: پیش‌فرض chrome؛ وقتی روش «از مرورگر» انتخاب شد فیلد مرورگر نمایش داده شود.
- مرورگرهای شناخته‌شده در yt-dlp نصب‌شده: brave، chrome، chromium، edge، opera، vivaldi، whale، firefox، safari. امکان استفاده به نصب مرورگر و پشتیبانی سیستم اجرای backend وابسته است.
- انتخاب مرورگر برای خواندن کوکی مرورگر ماشین اجرای backend است، نه انتخاب مرورگر بازکردن لینک یا مرورگر کاربر یک وب‌سایت.
- download.cookies_file: مسیر فایل Netscape cookies.txt، پیش‌فرض null. اگر مقدار داشته باشد نسبت به cookies_from_browser اولویت دارد؛ کد وجود فایل و کوکی احراز هویت YouTube را بررسی می‌کند.
- برای حالت بدون کوکی هر دو مقدار cookies_file و cookies_from_browser باید null باشند.
- این تنظیمات کوکی فقط در مسیر دانلود YouTube استفاده می‌شوند؛ Castbox آنها را دریافت نمی‌کند.
- download.js_runtimes: پیش‌فرض node؛ مقدار مستقیماً به yt-dlp ارسال می‌شود.
- download.remote_components: پیش‌فرض null؛ مقدار اختیاری مستقیماً به yt-dlp ارسال می‌شود.
خروجی: raw/{source_id}.{ext}، metadata.json، به‌روزرسانی manifests/speakers.csv و manifests/sources.csv.

## ۲. تبدیل / convert
الزامی: speaker_id و source_id. ورودی از raw.path در metadata خوانده می‌شود.
اختیاری: --overwrite؛ audio.sample_rate پیش‌فرض 44100 Hz.
خروجی: wav/{source_id}.wav؛ اولین stream صوتی ورودی، استریو، PCM 16-bit. ویدئو کنار گذاشته می‌شود. وضعیت conversion در metadata تکمیل می‌شود.

## ۳. جداسازی / separate
الزامی: speaker_id و source_id؛ فایل wav/{source_id}.wav باید موجود باشد.
گزینه‌ها:
- separation.model: نام checkpoint مدل، پیش‌فرض model_bs_roformer_ep_317_sdr_12.9755.ckpt.
- separation.checkpoints_dir: مسیر checkpointها؛ پیش‌فرض داخلی checkpoints، در YAML فعلی نیست.
- separation.preset: پیش‌فرض null.
- separation.use_autocast: پیش‌فرض false.
- audio.chunk_seconds: قطعه‌بندی موقت پردازش، پیش‌فرض 180 ثانیه؛ مدت segment نهایی نیست.
- audio.sample_rate: پیش‌فرض 44100 Hz.
- --keep-work-dir: پیش‌فرض false؛ نگهداری فایل‌های موقت، با موفقیت مرحله و مقدار false پاک می‌شوند.
- --overwrite: پیش‌فرض false.
خروجی: separated/{source_id}/vocals.wav و instrumental.wav، به‌روزرسانی metadata و رجیستری.

## ۴. تشخیص گوینده / diarize
الزامی: speaker_id و source_id؛ ورودی separated/{source_id}/vocals.wav است.
گزینه‌های اصلی:
- --num-speakers: تعداد گوینده‌های مورد انتظار، عدد صحیح مثبت؛ خالی یعنی تشخیص خودکار. بر diarization.num_speakers اختیاری در YAML اولویت دارد. وقتی CLI تعیین شود expected_num_speakers تحلیل کیفیت را هم تعیین می‌کند.
- --save-evidence / --no-save-evidence: ذخیره evidence مدل، پیش‌فرض true.
- --quality-analysis / --no-quality-analysis: تحلیل کیفیت خودکار، پیش‌فرض true.
- تحلیل کیفیت روشن نیازمند ذخیره evidence روشن است؛ UI این وابستگی را اعمال کند.
- --overwrite: پیش‌فرض false.
تنظیمات Advanced:
- diarization.model: pyannote/speaker-diarization-3.1.
- diarization.device: auto / cpu / cuda؛ کلید در YAML فعلی نیست. نبود آن یعنی CUDA اگر موجود باشد، وگرنه CPU.
- diarization.token_env: نام متغیر محیطی توکن، پیش‌فرض HF_TOKEN؛ fallback HUGGINGFACE_TOKEN. فایل .env پروژه هم خوانده می‌شود. این مقدار نام متغیر است، خود توکن نیست.
- diarization.cache_dir: checkpoints/huggingface.
- audio.diarization_sample_rate: 16000 Hz برای ورودی مدل؛ به معنی sample rate همه فایل‌های خروجی نیست.
- diarization.save_json: true؛ ذخیره annotation JSON.
- diarization.save_segments: true؛ ساخت WAVها و manifest نهایی.
- diarization.segment_padding_sec: 0.25 ثانیه در هر طرف کلیپ، با رعایت مرز فایل.
- diarization.segment_fade_sec: 0.005 ثانیه fade لبه‌ها.
- diarization.segment_min_duration_sec: 0.05؛ segment کوتاه‌تر از این مقدار WAV نمی‌شود.
- اگر کیفیت فعال باشد diarization_quality.enabled هم باید true باشد. صرفاً false کردن enabled در YAML، اجرای خودکار را خاموش نمی‌کند و می‌تواند خطا بدهد؛ خاموش‌کردن از گزینهٔ CLI انجام شود.
خروجی‌ها:
- annotation/diarization.rttm: همیشه.
- annotation/diarization.json: اگر save_json فعال باشد؛ source_id، audio، speaker_count، speakers، segment_count و segments.
- diagnostics/evidence/manifest.json و آرایه‌های .npy: اگر evidence فعال باشد.
- diagnostics/quality/: اگر تحلیل کیفیت فعال باشد.
- final/segments/{SPEAKER_LABEL}/*.wav و final/manifest.csv و manifest.json: اگر save_segments فعال باشد.
- final شامل segmentهایی است که با پنجره‌های مشکوک رتبه‌بندی‌شده یا detected_overlap تلاقی ندارند. missed_overlap_candidate به تنهایی باعث حذف نمی‌شود. عنوان مناسب UI: «خروجی نهایی پس از فیلتر خودکار»؛ این خروجی تضمین کیفیت یا تأیید انسانی نیست.

## ۵. تحلیل مجدد کیفیت / analyze-diarization
روی vocals و annotation موجود کار می‌کند؛ مدل diarization را دوباره اجرا نمی‌کند. evidence ذخیره‌شده را استفاده می‌کند، یا features-file اختصاصی را می‌خواند.
گزینه‌ها:
- speaker_id و source_id: الزامی.
- --top-k: عدد صحیح مثبت؛ پیش‌فرض 30، تعداد موارد مشکوک صادرشده.
- --min-score: از 0 تا 1؛ پیش‌فرض 0.
- --export-review-clips / --no-export-review-clips: اگر مشخص نشود از تنظیم YAML استفاده می‌کند؛ پیش‌فرض YAML true.
- --features-file: مسیر JSON ویژگی‌های خارجی، اختیاری؛ در صورت تعیین، adapter مربوط به evidence ذخیره‌شده انتخاب نمی‌شود.
- --reference-rttm: مسیر annotation مرجع برای ارزیابی، اختیاری.
- --collar: پیش‌فرض 0 ثانیه، ناحیهٔ اغماض مرزها در ارزیابی مرجع.
- --skip-overlap: پیش‌فرض false.
- --overwrite: پیش‌فرض false.
خروجی: quality_summary.json، suspicious_segments.json/csv، review_groups.json؛ گزارش overlap شامل overlap_candidates.json/csv و overlap_summary.json؛ کلیپ‌های مرور در review_clips/suspicious، groups و overlap، وقتی export فعال باشد.
محدودیت top-k مربوط به موارد مشکوک است، نه سقف تعداد کلیپ‌های overlap. review_score اولویت مرور است، نه احتمال خطا.
تحلیل مجدد به تنهایی final/segments را دوباره نمی‌سازد؛ برای اعمال فیلترهای جدید روی خروجی نهایی باید مسیر انتشار نهایی دوباره اجرا/پیاده‌سازی شود.

## ۶. بازسازی evidence / upgrade-diarization-evidence
speaker_id، source_id؛ --num-speakers اختیاری و --overwrite اختیاری. مدل را روی vocals دوباره اجرا می‌کند و evidence و تحلیل کیفیت را فعال نگه می‌دارد. این عملیات صرفاً خواندن یا تحلیل گزارش‌های قبلی نیست.

## تنظیمات کیفیت و نوع کنترل پیشنهادی
همه مقادیر پیش‌فرض در YAML انتهای سند آمده‌اند.
- enabled، embedding_analysis، overlap_analysis، temporal_analysis، segmentation_analysis، speech_activity_analysis، export_review_clips: Switch.
- expected_num_speakers: عدد صحیح مثبت یا خالی؛ تعداد مورد انتظار برای بررسی کیفیت، مستقل از شمار گویندهٔ مدل در صورت تنظیم صرفاً این کلید.
- minimum_segment_duration: حد مدت برای منطق تحلیل کیفیت؛ با حد صادرات WAV یکسان نیست.
- minimum_reference_segments: عدد صحیح حداقل 1؛ حد تعداد مرجع.
- short_turn_seconds، rapid_switch_seconds، short_gap_seconds، boundary_window_seconds، minimum_activity_interval، review_padding_seconds: ورودی عددی با واحد ثانیه، غیرمنفی.
- activity_threshold و activity_margin_threshold: بازه 0 تا 1.
- embedding_margin_threshold و cluster_margin_threshold: ورودی عددی غیرمنفی.
- weights.*: وزن‌های غیرمنفی برای رتبه‌بندی، در Advanced. شرح نام‌ها: speaker_margin ابهام گوینده، short_turn نوبت کوتاه، rapid_switch تغییر سریع، short_gap فاصله کوتاه، confirmed_overlap هم‌پوشانی تشخیص‌داده‌شده، missed_overlap هم‌پوشانی احتمالی ازدست‌رفته، spurious_overlap هم‌پوشانی احتمالاً کاذب، uncertain_overlap هم‌پوشانی نامطمئن، boundary_uncertainty ابهام مرز، activity_disagreement اختلاف فعالیت گفتار، cluster_margin ابهام خوشه‌بندی.

## خروجی‌ها برای طراحی صفحه‌ها
- فهرست speaker و source: metadata.json و CSVهای رجیستری؛ نام، زبان، جنسیت، نوع ورودی، URL/نام فایل، وضعیت مرحله‌ها و زمان تکمیل.
- صفحه source: فایل اصلی، WAV، vocals، instrumental، timeline annotation و خلاصه کیفیت.
- جدول segment نهایی از manifest.csv: index، speaker، start، end، duration_seconds، file، classification.
- مدت manifest مدت نوبت annotation است؛ طول واقعی WAV شامل padding است. مدت گفتار، جمع زمان annotation و جمع مدت WAV را با عنوان‌های جدا نمایش بده.
- آمار manifest.json: diarization_segment_count، published_segment_count، excluded_by_quality_review_count، wav_not_exported_count، speaker_counts، تعداد پنجره‌های کیفیت/overlap و padding.
- جدول مرور: rank، start/end، assigned_speaker، candidate_speaker، issue_types، review_score، ranking_group، warnings، review_clip؛ feature_scores و evidence_provenance در جزئیات Advanced.
- summary کیفیت: مدت audio، مدت گفتار، تعداد speaker/segment، تعداد candidate و exported_candidate، issue_counts، feature_availability، warnings و ارزیابی مرجع در صورت وجود.
- پوشه evidence و آرایه‌های مدل مناسب بخش فنی هستند؛ در صفحه اصلی داده خام آرایه‌ها نمایش داده نشود.

## قابلیت‌هایی که برای UI نیازمند پیاده‌سازی‌اند
- درصد پیشرفت، صف job، لغو/توقف و اجرای زنجیره‌ای مراحل در CLI فعلی endpoint آماده ندارند.
- تغییر label گوینده، ویرایش مرز segment و ذخیره تصمیم تأیید/رد برای هر مورد دستور آماده ندارند.
- تابع mark_source_reviewed در storage_metadata.py برای ثبت پایان مرور وجود دارد، ولی فرمان CLI برای آن وجود ندارد.
- تنظیمات speaker_chunker در default.yaml هستند و ابزارهای metadata/validation مربوط به prepared وجود دارند؛ اما runner یا فرمان chunker در run.py و src فعلی پیدا نشد. این بخش را «آینده/نیازمند اتصال» نمایش بده؛ وجود تنظیمات به معنی امکان اجرای فعلی آن نیست.
- انتخاب browser در نسخه وب به مرورگر backend اشاره دارد؛ برای دسترسی به فایل/کوکی مرورگر کاربر باید اجرای محلی یا سازوکار جدا فراهم شود.

## ساختار فایل‌ها
ریشه قابل تنظیم است. زیر data/speakers/{speaker_id}/:
```text
metadata.json
raw/{source_id}.{ext}
wav/{source_id}.wav
separated/{source_id}/vocals.wav
separated/{source_id}/instrumental.wav
diarization/{source_id}/annotation/diarization.json
diarization/{source_id}/annotation/diarization.rttm
diarization/{source_id}/final/manifest.json
diarization/{source_id}/final/manifest.csv
diarization/{source_id}/final/segments/{SPEAKER_LABEL}/*.wav
diarization/{source_id}/diagnostics/evidence/manifest.json
diarization/{source_id}/diagnostics/evidence/*.npy
diarization/{source_id}/diagnostics/quality/*.json
diarization/{source_id}/diagnostics/quality/*.csv
diarization/{source_id}/diagnostics/quality/review_clips/{suspicious,groups,overlap}/*.wav
```
رجیستری‌های مشترک: data/manifests/speakers.csv، sources.csv، chunks.csv (برای داده prepared در صورت وجود).

## درخواست طراحی
UI برای یک ابزار محلی مدیریت دادهٔ صوتی طراحی کن. ورودی ingest را با انتخاب «مسیر فایل محلی» یا «URL» بساز؛ کنترل‌های وابسته به هر حالت را نمایش بده. برای YouTube روش کوکی و انتخاب اختیاری مرورگر/فایل کوکی را در تنظیمات دانلود قرار بده. مراحل پردازش، پخش خروجی‌ها، timeline گوینده‌ها، مرور کیفیت و تنظیمات Advanced را پوشش بده. قابلیت‌های نیازمند پیاده‌سازی را مشخص کن. هیچ امکان تازه‌ای را به‌عنوان قابلیت موجود کد فرض نکن.

## نسخه کامل تنظیمات فعلی
بخش speaker_chunker در این YAML صرفاً تنظیمات موجود است؛ به مسیر اجرای فعلی CLI متصل نیست.
```yaml
storage:
  data_root: data
  schema_version: "1.0"

audio:
  sample_rate: 44100
  diarization_sample_rate: 16000
  chunk_seconds: 180

download:
  format: "251/140/bestaudio"
  audio_format: "opus"
  cookies_file: null
  cookies_from_browser: chrome
  js_runtimes: node
  remote_components: null

separation:
  model: model_bs_roformer_ep_317_sdr_12.9755.ckpt
  preset: null
  use_autocast: false

diarization:
  model: pyannote/speaker-diarization-3.1
  token_env: HF_TOKEN
  cache_dir: checkpoints/huggingface
  save_json: true
  save_segments: true
  segment_padding_sec: 0.25
  segment_fade_sec: 0.005
  segment_min_duration_sec: 0.05

diarization_quality:
  enabled: true
  expected_num_speakers: null
  embedding_analysis: true
  overlap_analysis: true
  temporal_analysis: true
  segmentation_analysis: true
  speech_activity_analysis: true
  minimum_segment_duration: 0.5
  minimum_reference_segments: 2
  short_turn_seconds: 0.7
  rapid_switch_seconds: 1.2
  short_gap_seconds: 0.15
  boundary_window_seconds: 0.25
  activity_threshold: 0.5
  activity_margin_threshold: 0.1
  minimum_activity_interval: 0.2
  embedding_margin_threshold: 0.1
  cluster_margin_threshold: 0.12
  review_padding_seconds: 0.5
  export_review_clips: true
  weights:
    speaker_margin: 1.0
    short_turn: 0.4
    rapid_switch: 0.6
    short_gap: 0.25
    confirmed_overlap: 0.3
    missed_overlap: 0.8
    spurious_overlap: 0.8
    uncertain_overlap: 0.7
    boundary_uncertainty: 0.5
    activity_disagreement: 0.7
    cluster_margin: 0.8

speaker_chunker:
  sample_rate: 16000
  allowed_audio_extensions:
    - .wav
    - .flac
    - .mp3
    - .m4a
    - .ogg
  chunk_sec: 4.0
  target_chunks_per_speaker: null
  target_policy: fixed
  capacity_ratio: 0.10
  min_target_chunks: 30
  max_target_chunks: 200
  silence_mode: zero
  random_seed: 42
  overwrite: false
  dry_run: false
  vad_backend: energy
  top_db: 35.0
  vad_floor_dbfs: -60.0
  min_speech_sec: 1.2
  merge_gap_sec: 0.25
  silero_threshold: 0.5
  silero_min_speech_ms: 250
  silero_min_silence_ms: 100
  silero_speech_pad_ms: 30
  min_active_speech_sec: 0.5
  min_active_speech_ratio: 0.125
  max_internal_silence_sec: null
  target_rms_dbfs: -25.0
  peak_limit: 0.98
  min_peak: 0.00001
  source_hop_sec: 2.0
  min_crop_start_gap_sec: 1.5
  duplicate_corr_threshold: 0.98
  speaker_duplicate_check_enabled: true
  speaker_duplicate_corr_threshold: 0.995
  speaker_duplicate_fingerprint_size: 2048
  speaker_duplicate_max_history: 5000
  max_chunks_per_segment: null
  concentration_warning_ratio: 0.35
  leading_silence_min_sec: 0.25
  leading_silence_max_sec: 1.50
  trailing_silence_min_sec: 0.30
  trailing_silence_max_sec: 1.50
  mode_weights:
    speech_start: 0.45
    leading_silence: 0.25
    trailing_silence: 0.20
    centered: 0.10
  end_boundary_check_enabled: true
  end_boundary_window_sec: 0.20
  end_boundary_search_sec: 0.80
  end_boundary_pause_min_sec: 0.15
  end_boundary_active_threshold_dbfs: -40.0
  end_boundary_pause_threshold_dbfs: -45.0
  end_boundary_max_tail_padding_sec: 1.0
  end_boundary_max_repairs_per_chunk: 1
  end_boundary_strict_modes:
    - leading_silence
    - trailing_silence
  end_boundary_allow_active_end_modes:
    - speech_start
    - centered
  start_boundary_enabled: true
  start_boundary_window_sec: 0.20
  start_boundary_search_sec: 0.80
  start_boundary_pause_min_sec: 0.15
  start_boundary_active_threshold_dbfs: -40.0
  start_boundary_pause_threshold_dbfs: -45.0
  start_boundary_max_head_padding_sec: 1.0
  start_boundary_max_repairs_per_chunk: 1
  mode_max_attempts: 12
  validate_output: true
```
