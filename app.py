from flask import Flask, render_template, request, Response, stream_with_context, jsonify
import time
import logging
import openai
from opentelemetry import trace
from opentelemetry.sdk.resources import SERVICE_NAME, Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.grpc.trace_exporter import OTLPSpanExporter
from opentelemetry.trace.propagation.tracecontext import TraceContextTextMapPropagator

client = openai.OpenAI()

app = Flask(__name__)

# Set up logging
logging.basicConfig(level=logging.DEBUG)
logger = logging.getLogger(__name__)

# Set up OpenTelemetry tracing
resource = Resource(attributes={SERVICE_NAME: "splunk-shelly-AI-assistant"})
provider = TracerProvider(resource=resource)
trace.set_tracer_provider(provider)
tracer = trace.get_tracer(__name__)
otlp_exporter = OTLPSpanExporter(endpoint="http://localhost:4317", insecure=True)
span_processor = BatchSpanProcessor(otlp_exporter)
provider.add_span_processor(span_processor)

# Initialize global variables
chat_history = [
    {"role": "system", "content": "Hello, I'm Shelly's Assistant; I (actually) run The Splunk T-Shirt Company. AMA"}]
GPT_model = "gpt-3.5-turbo"
GPT_temperature = 0.8
GPT_top_p = 0.5
active_spans = {}
span_contexts = {}


@app.route("/", methods=["GET"])
def index():
    return render_template("index.html", chat_history=chat_history)


@app.route("/chat", methods=["POST"])
def chat():
    content = request.json["message"]
    global GPT_model
    GPT_model = request.json["model"]
    chat_history.append({"role": "user", "content": content})
    return jsonify(success=True)


@app.route("/stream", methods=["GET"])
def stream():
    def generate():
        assistant_response_content = ""
        start_time = time.time()
        with tracer.start_as_current_span("call_gpt_model") as span:
            span_id = span.context.span_id
            carrier = {}
            TraceContextTextMapPropagator().inject(carrier)
            span_contexts[span_id] = carrier
            active_spans[span_id] = span
            logger.debug("stream(): span_id: %s", span_id)

            result = ""
            tokens_used = 0
            completion_tokens = 0
            prompt = chat_history[-1]["content"]
            with client.chat.completions.create(
                    model=GPT_model,
                    messages=chat_history,
                    stream=True,
                    temperature=GPT_temperature,
                    top_p=GPT_top_p,
            ) as stream:
                for chunk in stream:
                    if chunk.choices[0].delta and chunk.choices[0].delta.content:
                        token_text = chunk.choices[0].delta.content
                        result += token_text
                        tokens_used += len(token_text.split())
                        completion_tokens += 1
                        span.set_attribute("tokens_used_partial", tokens_used)
                        span.set_attribute("completion_tokens_partial", completion_tokens)
                        assistant_response_content += chunk.choices[0].delta.content
                        yield f"data: {chunk.choices[0].delta.content}\n\n"
                    if chunk.choices[0].finish_reason == "stop":
                        break

                end_time = time.time()
                latency = end_time - start_time
                span.set_attribute("id", chunk.id)
                span.set_attribute("GPT-model", chunk.model)
                span.set_attribute("GPT-temperature", GPT_temperature)
                span.set_attribute("GPT-top_p", GPT_top_p)
                span.set_attribute("prompt", prompt)
                span.set_attribute("response", result)
                span.set_attribute("latency", latency)
                span.set_attribute("tokens_used", tokens_used)
                span.set_attribute("completion_tokens", completion_tokens)

            chat_history.append({"role": "assistant", "content": assistant_response_content})

    return Response(stream_with_context(generate()), mimetype="text/event-stream")


@app.route("/satisfaction", methods=["POST"])
def satisfaction():
    data = request.json
    span_id = list(active_spans.keys())[0]
    logger.debug("satisfaction(): span_id: %s", span_id)
    score = data.get("score")
    span_context = span_contexts.get(span_id)

    if span_context:
        extracted_context = TraceContextTextMapPropagator().extract(span_context)
        with tracer.start_as_current_span("satisfaction", context=extracted_context) as span:
            span.set_attribute("user_satisfaction", score)
            span.end()
            del active_spans[span_id]
            del span_contexts[span_id]
            return jsonify(success=True)
    else:
        return jsonify(success=False, error="Span not found"), 404


@app.route("/reset", methods=["POST"])
def reset_chat():
    global chat_history
    chat_history = [{"role": "system",
                     "content": "Hello, I'm Shelly's Assistant; I (actually) run The Splunk T-Shirt Company. AMA"}]
    return jsonify(success=True)
