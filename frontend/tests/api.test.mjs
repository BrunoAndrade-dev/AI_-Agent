import assert from "node:assert/strict";
import { test } from "node:test";
import { StoreApi, ApiError } from "../src/lib/api.ts";

function respond(body, status = 200, headers = {}) {
    return new Response(JSON.stringify(body), {
        status,
        headers: { "Content-Type": "application/json", ...headers },
    });
}

test("login uses cookies and replaces CSRF after authentication", async () => {
    const calls = [];
    globalThis.fetch = async (url, options) => {
        calls.push({ url, options });
        if (calls.length === 1)
            return respond({
                authenticated: false,
                csrf_token: "before",
                expires_at: null,
            });
        if (calls.length === 2)
            return respond({
                authenticated: true,
                csrf_token: "after",
                expires_at: null,
            });
        return new Response(null, { status: 204 });
    };
    const api = new StoreApi("http://localhost:8000/api");
    await api.login("example-only");
    await api.logout();
    assert.equal(calls[1].options.headers["X-CSRFToken"], "before");
    assert.equal(calls[2].options.headers["X-CSRFToken"], "after");
    assert(calls.every((call) => call.options.credentials === "include"));
    assert.deepEqual(JSON.parse(calls[1].options.body), {
        access_token: "example-only",
    });
});

test("CSRF rejection refreshes the token once without changing the message UUID", async () => {
    const calls = [];
    globalThis.fetch = async (_url, options) => {
        calls.push(options);
        if (calls.length === 1 || calls.length === 3)
            return respond({
                csrf_token: `csrf-${calls.length}`,
                authenticated: true,
                expires_at: null,
            });
        if (calls.length === 2)
            return respond(
                {
                    error: {
                        code: "permission_denied",
                        message: "CSRF Failed: incorrect token",
                    },
                },
                403,
            );
        return respond(
            {
                turn: { id: "turn", text: "Resposta", status: "ok" },
                replayed: false,
            },
            201,
        );
    };
    const job = {
        conversationId: "conversation",
        requestId: "same-uuid",
        text: "E no PIX?",
    };
    await new StoreApi().send(job);
    assert.equal(calls.length, 4);
    assert.equal(calls[1].body, calls[3].body);
    assert.equal(calls[3].headers["X-CSRFToken"], "csrf-3");
    assert(!calls[3].body.includes("customer_id"));
});

test("persisted 503 replies are returned as turns; infrastructure errors remain errors", async () => {
    const api = new StoreApi();
    globalThis.fetch = async (_url, options) =>
        options.method === "GET"
            ? respond({
                  authenticated: true,
                  csrf_token: "csrf",
                  expires_at: null,
              })
            : respond(
                  {
                      turn: {
                          id: "failed-turn",
                          text: "Modelo indisponível.",
                          status: "model_unavailable",
                      },
                      replayed: false,
                  },
                  503,
              );
    const job = {
        conversationId: "conversation",
        requestId: "uuid",
        text: "Olá",
    };
    assert.equal((await api.send(job)).turn.status, "model_unavailable");
    globalThis.fetch = async () =>
        respond(
            { error: { code: "service_unavailable", message: "Sem dados." } },
            503,
        );
    await assert.rejects(
        api.send(job),
        (error) => error instanceof ApiError && error.status === 503,
    );
});

test("network failures do not automatically resend a potentially accepted message", async () => {
    const api = new StoreApi();
    globalThis.fetch = async () =>
        respond({ authenticated: true, csrf_token: "csrf", expires_at: null });
    await api.session();
    let sends = 0;
    globalThis.fetch = async () => {
        sends += 1;
        throw new TypeError("network");
    };
    await assert.rejects(
        api.send({ conversationId: "id", requestId: "uuid", text: "Olá" }),
        (error) => error instanceof ApiError && error.status === 0,
    );
    assert.equal(sends, 1);
});

test("rate-limit delay is exposed for a controlled retry", async () => {
    globalThis.fetch = async () =>
        respond({ error: { code: "throttled", message: "Aguarde." } }, 429, {
            "Retry-After": "17",
        });
    await assert.rejects(
        new StoreApi().session(),
        (error) => error instanceof ApiError && error.retryAfter === 17,
    );
});
