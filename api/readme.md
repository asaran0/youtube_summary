Two ways, matching the two batch endpoints.
curl -X 'POST' \
  'http://127.0.0.1:8000/api/v1/qa-videos' \
  -H 'accept: application/json' \
  -H 'Content-Type: application/json' \
  -d '{
    "qa_pairs": [
      {
        "question": "What is the difference between JDK, JRE, and JVM?",
        "answer": "JVM (Java Virtual Machine) is the engine that drives the Java code by converting bytecode into machine language. JRE (Java Runtime Environment) is a software package that provides the JVM along with Java binaries and other libraries to run a Java application. JDK (Java Development Kit) is a full-featured software development kit that includes the JRE plus development tools like the compiler (javac) and debuggers needed to write and compile Java programs."
      }
    ],
    "title": "Java Interview Question: JDK VS JRE VS JVM",
    "language": "en",
    "output_mode": "reel",
    "tts_backend": "xtts",
    "voice_sample": "assets/clean_voice.wav",
    "keep_temp": false
  }'

Two ways, matching the two batch endpoints.

**1. Batch via JSON (`qa_pairs` inline)**

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/qa-videos/batch' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "java_interview",
    "questions_per_part": 5,
    "language": "en",
    "output_mode": "reel",
    "tts_backend": "xtts",
    "voice_sample": "assets/clean_voice.wav",
    "qa_pairs": [
      {"question": "What is JVM?", "answer": "JVM is the engine that runs Java bytecode."},
      {"question": "What is JDK?", "answer": "JDK is the full development kit including JRE plus compiler and debugger."},
      {"question": "What is JRE?", "answer": "JRE is the runtime environment needed to run Java applications."},
      {"question": "What is garbage collection?", "answer": "It is automatic memory management that reclaims unused objects."},
      {"question": "What is a class loader?", "answer": "It is the JVM component that loads class files at runtime."},
      {"question": "What is multithreading?", "answer": "It is running multiple threads concurrently within a program."}
    ]
  }'
```

With `questions_per_part: 5` and 6 questions, that creates **2 jobs**: `java_interview_part1` (first 5) and `java_interview_part2` (last 1).

Response gives you the `batch_id` plus each part's `job_id`.

**2. Batch via file upload** (this is the "give a file name" path you originally asked for)

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/qa-videos/batch/upload' \
  -F 'file=@assets/sample_interview_qa.txt' \
  -F 'name=java_interview' \
  -F 'questions_per_part=5' \
  -F 'language=en' \
  -F 'output_mode=reel' \
  -F 'tts_backend=xtts' \
  -F 'voice_sample=assets/clean_voice.wav'
```

`file` must contain plain `Q: ...` / `A: ...` text, same format as your existing `--file` CLI input.

**3. Check batch status**

```bash
curl 'http://127.0.0.1:8000/api/v1/qa-videos/batch/<batch_id>'
```

Returns each part's individual status (`queued`/`running`/`done`/`failed`) plus an `overall_status`. Once a part is `done`, grab its `job_id` from this response and download with the regular single-video endpoints:

```bash
curl -OJ 'http://127.0.0.1:8000/api/v1/qa-videos/<job_id>/video'
```

As before, both are also doable through `/docs` if you'd rather avoid escaping text by hand — the file-upload one especially is much easier there since it gives you an actual file picker.
**1. Batch via JSON (`qa_pairs` inline)**

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/qa-videos/batch' \
  -H 'Content-Type: application/json' \
  -d '{
    "name": "java_interview",
    "questions_per_part": 5,
    "language": "en",
    "output_mode": "reel",
    "tts_backend": "xtts",
    "voice_sample": "assets/clean_voice.wav",
    "qa_pairs": [
      {"question": "What is JVM?", "answer": "JVM is the engine that runs Java bytecode."},
      {"question": "What is JDK?", "answer": "JDK is the full development kit including JRE plus compiler and debugger."},
      {"question": "What is JRE?", "answer": "JRE is the runtime environment needed to run Java applications."},
      {"question": "What is garbage collection?", "answer": "It is automatic memory management that reclaims unused objects."},
      {"question": "What is a class loader?", "answer": "It is the JVM component that loads class files at runtime."},
      {"question": "What is multithreading?", "answer": "It is running multiple threads concurrently within a program."}
    ]
  }'
```

With `questions_per_part: 5` and 6 questions, that creates **2 jobs**: `java_interview_part1` (first 5) and `java_interview_part2` (last 1).

Response gives you the `batch_id` plus each part's `job_id`.

**2. Batch via file upload** (this is the "give a file name" path you originally asked for)

```bash
curl -X POST 'http://127.0.0.1:8000/api/v1/qa-videos/batch/upload' \
  -F 'file=@questions/questions/python basics.txt' \
  -F 'name=Python basic interview question answers ' \
  -F 'questions_per_part=20' \
  -F 'language=en' \
  -F 'output_mode=full' \
  -F 'tts_backend=xtts' \
  -F 'voice_sample=assets/clean_voice.wav'
```

`file` must contain plain `Q: ...` / `A: ...` text, same format as your existing `--file` CLI input.

**3. Check batch status**

```bash
curl 'http://127.0.0.1:8000/api/v1/qa-videos/batch/<batch_id>'
```

Returns each part's individual status (`queued`/`running`/`done`/`failed`) plus an `overall_status`. Once a part is `done`, grab its `job_id` from this response and download with the regular single-video endpoints:

```bash
curl -OJ 'http://127.0.0.1:8000/api/v1/qa-videos/<job_id>/video'
```

As before, both are also doable through `/docs` if you'd rather avoid escaping text by hand — the file-upload one especially is much easier there since it gives you an actual file picker.