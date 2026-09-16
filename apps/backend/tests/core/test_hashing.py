from app.core.hashing import Argon2Hasher, build_hasher

MOT_DE_PASSE = "un-mot-de-passe-de-test-assez-long"


def fabrique(time_cost: int = 1, max_concurrency: int = 2) -> Argon2Hasher:
    return build_hasher(
        time_cost=time_cost,
        memory_cost_kib=8192,
        parallelism=1,
        max_concurrency=max_concurrency,
    )


async def test_hash_produces_a_distinct_digest_for_the_same_password() -> None:
    hacheur = fabrique()

    premier = await hacheur.hash(MOT_DE_PASSE)
    second = await hacheur.hash(MOT_DE_PASSE)

    assert premier != second
    assert premier.startswith("$argon2id$")


async def test_verify_accepts_the_right_password_and_rejects_the_others() -> None:
    hacheur = fabrique()

    empreinte = await hacheur.hash(MOT_DE_PASSE)

    assert await hacheur.verify(empreinte, MOT_DE_PASSE) is True
    assert await hacheur.verify(empreinte, "un-autre-mot-de-passe") is False


async def test_verify_returns_false_when_the_stored_digest_is_malformed() -> None:
    hacheur = fabrique()

    accorde = await hacheur.verify("pas-une-empreinte-argon2", MOT_DE_PASSE)

    assert accorde is False


async def test_needs_rehash_is_true_when_the_parameters_changed() -> None:
    ancien = fabrique(time_cost=1)
    recent = fabrique(time_cost=3)

    empreinte = await ancien.hash(MOT_DE_PASSE)

    assert ancien.needs_rehash(empreinte) is False
    assert recent.needs_rehash(empreinte) is True


def test_needs_rehash_is_true_when_the_stored_digest_is_malformed() -> None:
    hacheur = fabrique()

    assert hacheur.needs_rehash("pas-une-empreinte-argon2") is True


async def test_verify_dummy_completes_without_revealing_anything() -> None:
    hacheur = fabrique()

    await hacheur.verify_dummy()
