# Spike: file storage with expiring links, and bank-number encryption

Throwaway code for ticket T-01 of the `system-design` task. It answers two
questions and is never merged. The written records, with results and the
recommendation, are on the task branch:

- `docs/tasks/system-design/spikes/storage-and-links.md`
- `docs/tasks/system-design/spikes/bank-number-encryption.md`

Run everything (needs Python 3.13 and access to PyPI; no other service):

    ./run.sh

Run one question only:

    ./run.sh tests/test_links.py tests/test_storage.py tests/test_files_app.py
    ./run.sh tests/test_bank.py

Check that each test really fails when its behaviour is broken (applies one
deliberate break at a time to a temporary copy and reruns the tests):

    .venv/bin/python experiments/break_each_behaviour.py

The alternative that was weighed for links (the object store's own presigned
URLs):

    .venv/bin/python experiments/presigned_on_moto.py
