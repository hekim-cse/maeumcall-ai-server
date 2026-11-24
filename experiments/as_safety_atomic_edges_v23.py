"""Remove only the displayed number reference in the event description."""

from functools import partial
from hashlib import sha256

from experiments import as_safety_atomic_edges_v19 as runtime
from experiments import as_safety_atomic_edges_v20 as single_source
from experiments import as_safety_atomic_edges_v22 as prior
from experiments.as_safety_runner import Call, Experiment, Model

NAME = "as-safety-eb-event-reference-v23"
PRIOR_JOURNAL_SHA = "ceb22990bbbf5fc53adf690fc631f40c2e1e212a3afb96fd74c547984123cd39"
SOURCES = (
    "experiments/as_safety_atomic_edges_v23.py",
    "experiments/as_safety_atomic_edges_v19.py",
    "docs/portfolio/nlu_safety_eb_event_reference_v23_method.md",
)


def make_experiment() -> Experiment:
    policy, reference_calls, upstream_sha = prior.requests()
    reference_sha = prior.load_protocol(reference_calls, upstream_sha)
    if sha256(prior.JOURNAL.read_bytes()).hexdigest() != PRIOR_JOURNAL_SHA:
        raise ValueError("reference journal differs")
    calls = []
    for name, (pair, messages, schema, _) in reference_calls.items():
        old = f"위험 사건 E: 1번 | {pair.event['quote']}"
        new = f"위험 사건 E: {pair.event['quote']}"
        lines = messages[1]["content"].splitlines()
        if lines.count(old) != 1:
            raise ValueError(f"unexpected event reference: {name}")
        lines[lines.index(old)] = new
        adapted = [messages[0], {**messages[1], "content": "\n".join(lines)}]
        calls.append(Call(name, adapted, schema, partial(single_source.validate, pair=pair)))
    return Experiment(
        NAME,
        Model(runtime.MODEL_SHA, runtime.CONTAINER, runtime.server),
        policy,
        tuple(calls),
        SOURCES,
        {"protocol_sha256": reference_sha, "journal_sha256": PRIOR_JOURNAL_SHA},
    )


if __name__ == "__main__":
    make_experiment().cli()
