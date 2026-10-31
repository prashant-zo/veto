# 0001 muse spark open as the judge

status: accepted

The judge runs on Muse Spark Open through Baseten (meta-models/muse-spark-open-1026).
The client talks the OpenAI chat API, so an endpoint is just base_url, key and model.

Why: it is the key that works, and open weights mean teams can host it themselves later.
Other models can plug in through the same settings, but demo and eval use only Muse.

Update: Muse Spark 1.3 through the Meta Model API (https://api.meta.ai/v1) also works.
It is the fallback when Baseten is down, and the second row in the eval.
