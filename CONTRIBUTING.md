Contributing to HF Propagation

Bug reports, documentation corrections, and improvements are welcome.
The project is maintained by **Chris Parrish (KK4TSS)**.

## Report a bug

Check the [README troubleshooting section](README.md#troubleshooting) and
[existing issues](https://github.com/KK4TSS/Badger-HF-Propagation/issues) first.
If the problem has not been reported, open an issue using the **Bug report** template.

Include:

- App version and Badgeware firmware version.
- Steps to reproduce the problem, expected behavior, and what happened.
- Exact screen messages and relevant observation timestamps.
- Whether the badge was on USB or battery power, and whether the problem followed
  startup, a button press, or a scheduled wake.
- A screenshot or photo when it helps explain the problem.

Never post Wi-Fi passwords, tokens, or other private information.

## Suggest a feature

Use the **Feature request** issue template. Explain the problem you want to solve,
how the proposed feature would help, and any alternatives you have considered.
Keep the badge's small e-paper display, battery life, and intermittent Wi-Fi in mind.
Discuss larger changes in an issue before starting implementation.

## Submit a change

1. Fork the repository and create a branch for your change.
2. Keep the change focused on one fix or improvement.
3. Update documentation when behavior or installation instructions change.
4. Add or update tests for changed behavior where practical.
5. Run the checks below and open a pull request against the default branch.

In your pull request, describe the problem, what changed, and how you tested it.
Link any related issue. For visible changes, include a screenshot or badge photo.
Say explicitly which checks were performed on hardware and which were desktop tests.

## Run the checks

From the repository root, using Python 3.11 or newer:

```sh
PYTHONDONTWRITEBYTECODE=1 PYTHONPATH=hf_propagation python3 -m unittest discover -s tests
python3 tools/package_app.py
```

The test suite uses Python's standard library. GitHub Actions runs it on Python
3.11–3.14 and verifies that the install ZIP builds.

Desktop tests simulate the badge runtime. Changes affecting Wi-Fi/TLS, controls,
lighting, the display, or wake/sleep behavior should also be checked on a
Badger 2350 running Badgeware v3. If you cannot test on hardware, note that in
the pull request.

## Project conventions

- Keep runtime code compatible with the badge's MicroPython environment.
- Preserve HTTPS certificate and hostname verification.
- Keep credentials in the device's existing `secrets.py`; never embed them in the app.
- Keep changes to readings, timestamps, and offline behavior clear to users.
- Include required app assets, including `font.png` and the bundled public CA certificate.
- Leave generated ZIPs, caches, and device state out of commits.
- Leave version changes and release tags to the maintainer unless agreed in the issue.

## License

Contributions to the app are accepted under its existing
[GNU GPL version 3 only license](LICENSE). Only submit material you have the right
to contribute, and preserve existing copyright and third-party notices.
The bundled public certificate has separate terms in
[THIRD_PARTY_NOTICES.md](THIRD_PARTY_NOTICES.md).
