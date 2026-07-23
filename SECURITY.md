# Security

## Scope

Use this repository as an integration demo. Do not treat the local token issuer, default secret, or in-memory client as production controls.

Keep the default services bound to loopback. Do not expose the default configuration to an untrusted network.

## Deployment Checklist

Complete these actions before deployment:

- replace `/demo-token` with a trusted identity provider;
- validate issuer, audience, signature, expiry, and subject on every request;
- rebuild tenant, role, data scope, and tool permissions from a trusted server-side source;
- bind every thread and continuation operation to its authenticated owner;
- authorize each tool before reading or changing data;
- add rate, concurrency, body-size, duration, and output limits;
- enable HTTPS and restrict CORS to exact origins;
- add audit events without recording raw tokens or sensitive content;
- map internal exceptions to generic external errors;
- place the Agent endpoint behind a trusted BFF or API gateway when possible;
- review dependency advisories and the applicable product licenses.

Do not commit `.env` files, access tokens, private keys, private license tokens, user data, or generated traces containing sensitive data.

## Reporting

Enable private vulnerability reporting in the repository settings before accepting external users. Publish a security contact when the project gains maintainers.
