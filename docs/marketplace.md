# Community profile marketplace (F9 / v0.9.0 R1)

Browse and install YAML profiles contributed by the community —
without leaving the CLI or GUI, and without trusting any code to
execute on your machine. The catalog is SHA-pinned per entry; a
profile that does not match its declared hash is refused before
the file lands on disk.

## Trust model

* **HTTPS-only.** The catalog and every profile URL it references
  are forced to `https://`. A non-HTTPS URL is rejected before
  any bytes are read, regardless of where the URL came from.
* **SHA-256 pinning.** Each catalog entry includes a hex SHA-256
  of the profile YAML it points at. `install` downloads, hashes,
  and refuses to write the file if the digest does not match.
* **Ed25519 signatures (v1.2.0 Task 25).** Catalog entries may carry
  a `signature` field — 64 raw bytes of Ed25519, hex-encoded — produced
  by the marketplace operator's offline private key over the entry's
  `sha256` field. When signature enforcement is on
  (`require_signature=True` on the `install()` API or
  `VIDEO_UNIQ_REQUIRE_SIGNED_PROFILES=1` in the environment), unsigned
  entries and entries whose signature doesn't verify against any
  bundled marketplace public key are rejected. See § Signing policy.
* **Schema-validated.** Even after a SHA match, the YAML is run
  through `Profile.model_validate` (with `extra=forbid`) *before*
  the atomic rename into the per-user profile dir. A malformed
  profile never reaches its final filename.
* **No code execution.** Profiles are declarative YAML; loading
  one only invokes the pydantic schema. There is no path by which
  a marketplace entry can execute arbitrary code on your machine.
* **No silent fall-through.** Transport errors (network down,
  TLS failure) fall back to the local cache → in-wheel bootstrap,
  in that order. Configuration-shape errors (oversized payload,
  non-HTTPS URL, JSON parse failure) propagate as fatal — we do
  not serve a stale catalog for a misconfigured upstream.

## CLI

```bash
video-uniq profile list-community          # cached + sorted by id
video-uniq profile list-community --refresh
video-uniq profile show cid_aware          # inspect before install
video-uniq profile install cid_aware       # → ~/.config/video_uniquifier/profiles/
video-uniq profile install cid_aware --dest /custom/dir --overwrite
video-uniq profile install-dir             # print default install dir
video-uniq profile purge-cache             # force re-fetch on next call
```

## GUI

The Profile Editor screen has a **Browse community…** button.
The dialog lists every catalog entry, shows the URL and SHA on
selection, and installs into your per-user profile dir on click.
Installed profiles appear in the dropdown without restart.

## Catalog format

```json
{
  "version": 1,
  "entries": [
    {
      "id": "cid_aware",
      "name": "CID-aware (balanced)",
      "description": "Conservative micro-transforms…",
      "url": "https://raw.githubusercontent.com/…/cid_aware.yaml",
      "sha256": "d4cdb9e4877387ec259524da6ef9806c…",
      "author": "video-uniquifier core",
      "tags": ["cid", "balanced"],
      "version": "1.0.0",
      "min_video_uniquifier_version": "0.9.0"
    }
  ]
}
```

The schema lives at `core/profile_marketplace.py::Catalog` (with
`extra=forbid`); validation rejects any unknown fields.

## Where things live

| Item                 | Path                                                       |
|----------------------|------------------------------------------------------------|
| Bootstrap catalog    | `<wheel>/video_uniquifier/marketplace/catalog.json`           |
| Cached catalog       | `~/.cache/video_uniquifier/marketplace/catalog.json`          |
| Installed profiles   | `~/.config/video_uniquifier/profiles/<id>.yaml` (default)     |
| Project catalog      | `https://raw.githubusercontent.com/Hostlife22/video-uniquifier/main/src/video_uniquifier/marketplace/catalog.json` |

The bootstrap catalog ships inside the wheel so a fresh install
without network reachability still lists a handful of starter
profiles. The same catalog is hosted in the project repository; a successful
network fetch wins on refresh.

## Contributing a profile

1. Author the YAML against the schema documented in
   [Profiles](profiles.md). Run `video-uniq preflight <some_source>
   --profile <your.yaml>` to sanity-check.
2. Compute the SHA-256 of the final YAML:

    ```bash
    shasum -a 256 your_profile.yaml
    ```

3. Open a PR against `Hostlife22/video-uniquifier` updating
   `src/video_uniquifier/marketplace/catalog.json` with a new entry.
   Include `author`, a 1-line
   `description`, and at least one `tag`.
4. Mention the YAML's hosting URL — a raw GitHub URL is the
   canonical choice. The URL **must** be HTTPS.

Reviewers will install the profile from your branch, run it
against a reference source, and verify the SHA matches.

## Signing policy (v1.2.0 Task 25)

Catalog entries may be signed by the marketplace operator. The bundled
public key set lives at `src/video_uniquifier/keys/marketplace.pub`
(shipped with the wheel) — one hex-encoded Ed25519 public key per
non-comment line, allowing multiple keys during rotation.

### What gets signed

The signature covers the ASCII bytes of the entry's `sha256` field —
the same hex string that pins the YAML body.  Binding the signature to
the SHA means a single signature simultaneously authenticates the URL
target and the body content: an attacker who flips the `url` to a
different YAML must also flip the `sha256` to match, which breaks the
signature unless they also have the operator's private key.

### Signing workflow

```bash
# One-off setup: generate the operator's keypair.
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
from cryptography.hazmat.primitives import serialization
priv = ed25519.Ed25519PrivateKey.generate()
print('PRIVATE (keep offline!):',
      priv.private_bytes(serialization.Encoding.Raw,
                         serialization.PrivateFormat.Raw,
                         serialization.NoEncryption()).hex())
print('PUBLIC (ship in marketplace.pub):',
      priv.public_key().public_bytes(serialization.Encoding.Raw,
                                     serialization.PublicFormat.Raw).hex())
"

# Per-entry: sign the body SHA.
python -c "
from cryptography.hazmat.primitives.asymmetric import ed25519
priv = ed25519.Ed25519PrivateKey.from_private_bytes(bytes.fromhex(PRIV_HEX))
sha256_hex = '<the entry\\'s sha256 field>'
print(priv.sign(sha256_hex.encode('ascii')).hex())
"
```

Paste the resulting 128-char hex string into the catalog entry's
`signature` field.

### Key rotation

1. Generate a new keypair.
2. Append the new public key to `marketplace.pub` **above** the old
   one.  Both keys remain valid; verification accepts a signature
   against any listed key.
3. Re-sign every active catalog entry with the new private key.
4. Once every entry is re-signed, drop the old public key from
   `marketplace.pub` in the next video-uniquifier release.
5. Permanently destroy the old private key.

### Enforcement

Signature verification is opt-in to preserve backwards compatibility
with the v0.9 catalog format.  Operators who want signature-only mode:

* Pass `require_signature=True` to `install(...)` in code.
* Or export `VIDEO_UNIQ_REQUIRE_SIGNED_PROFILES=1` in the shell that
  spawns `video-uniq` / `video-uniq-gui`.

The `cryptography` package (PyCA reference) is bundled as the
`[crypto]` extra.  Installs without the extra can still use unsigned
catalogs; turning on enforcement on a non-`[crypto]` install raises a
clear error pointing at the missing dependency.
