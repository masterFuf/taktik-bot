"""No handle of a real test account, and no serial of a real phone, in this public repository.

Tests use invented handles, and examples a placeholder serial (`emulator-5554`). What is guarded is
kept as SHA-256 digests so that this guard does not publish what it guards: every word of the
scanned files that could be a handle or a serial is hashed and looked up.
"""

import functools
import hashlib
import pathlib
import re

_CORE = pathlib.Path(__file__).resolve().parents[2]

#: Guarded in every source file of the repository.
_EVERYWHERE = {
    "bc079ff1d680112a4f65c1f1f2b6c18d00562c3e8a45c738714f08d65360bd21",
    # A public creator and the fan accounts a TikTok search served next to hers.
    "1a04b344228d6ca6efc4d962b39e7b89976bf92e394de86441438a1ca2453f4b",
    "d227f250d0385626bdf9dd1336693bbf986c6757e9b6987632acec77f36554fa",
    "339c9a03a45f76d2bbc96d3e6be11b59076d2abc550a02adc72db90a0713c356",
    "1e6e133808f32e4272a5c793ee9078914296289cbd51097dce55247160b2342c",
    "4cdbb049a0b6785e2ab60037faf7c2d4106f481acf8e5bbbaa469d285f7aa0f8",
    "d94cf837c4b2dce73ad5ad82242426eb7d9ed3d65130371f5f37f77fa3dfe6f0",
    "fa6465ab4a53ecff1bb586e0cbeee43e520e5b0bde9a11e5e0d6cd61ca342f73",
    "b1c1a4b336761961d59e2a900247a0a70ed1aba1d12e1849364f7420ba33e3b3",
    "95b92868858b53bd92fd0f537f22050bb581a8a061586845bf21a3627cd2ba25",
    # Accounts of the owner's clients, and the people their runs met on screen.
    "40ba63863ac7001aaf3ffae340b37c9ea927144a1cfcca9c07745ee68a849b0c",
    "9d90925e0458b2268a18ef1f82c0bd4f82286e411d6826272d7f5d4de8627dd2",
    "25b2a6f12ba281938b674cd000b132b0fe76299b0e4954652232bebd407516a1",
    "3cdab2964879d6e039c6f7359cf973fe27be21ac0f2996766fd4997bf59dfb6e",
    "ebc29bdf1eb424edea0ed0306069bd2316e34a36b4a2fb86785f5f164dc9709c",
    "bca951f50a6fc96c5eeabb339458ee934b4075864b481c13a78511ee939195b4",
    "5348196364e8bc2b4b8e05b0e7a76260f39b33dc5259a15f86051f66ee542e2f",
    "7714d04c546d2a44a7f88f94676560c5fac6e36a1e2cfe1d0c4666b2480d621b",
    "b145a07e356f9d88361dca147b1b549bd65a5011db50e386dd2b2c0f43a36842",
    "f273f526b31ab0a36f5a2d8243d574cf442b84b41e3e3d659f3c86a6b6963907",
    "b65cc24e7d26446085b51379c6b4c379e70976fa403b320c09f5c93447bee3a5",
    "e082253615eba9060262f2bb8c843ab7b29570e9b7660fcbc9f6915374d0409f",
    "67ca9e76778df047752065a2ee40ed7b2553a4853c03245d8585b70c6e3b5e0c",
    "36fff5224e0edce59e5556d840204bc596cb64c1957ab8cd09a4214ee47c1574",
    "ac543d298113aefc14131439d99a6e86816c1e91d5491e3f56ef7a28d7c8b7a2",
    "3e0fe06e679f8ecc745886243f2eaa691154b7c6c55cb6c455f55840958ab890",
    "95663f4194584133efe10ff439eea8d561920649b7fb77ecd2192206f41661e3",
    "349a98055c9a1f0bf7b858844ad3b007d5ca231038d7d65fbfcdb52a993445b1",
    "0c2de96f2436bdfd395b3976b1c900ab424b2c19c4b432bd971cfe071851b63b",
    "b5b38db1cf85f059b7e3a354b3036a5acc8ac516856caea5f84b0acc427747bf",
    "0088f3e56a7892c027a7c1c0d2d60e1dcbef6a95daec28f7efedd6fa2afb1ad6",
    "b35e3bbc519e8e6690407c36322290a667c33c03c13bb0cb7635c05d3bd7572d",
    "e36dbfe851f5adc588af63fc478048c26c2348e19a0f5b5ff9fdf554202e9735",
    "bd14c602fadd6feb515f4c7760018b97ad8a89795a8d3eec8a017ba706fea069",
    "eccbbd97497ac63b12a80ef6718f05a3922c33da6df11c0c0221fd9591d85bf6",
    "2d73cc6eb656709c4b0335efe43a9bb563d73861559fbe4632155f408edb3db4",
    "68867b1c7c86ea12a0c7e8d1f275d09facbdb56e0f11df1b467fc59654ceaca5",
    "d646fdd3d11e14c5ea3e654f9f61b5de4fc6ee6f061ca1147240fc242314081c",
    "256c28203094c9dad3e7e5581128aa1a730e0d9f96eb9a29995750949756a1a1",
    "d27d28e228efe58b1736b53e8309941cf83fb8fcf751bef667a68d02e7d34015",
    "9a22f15a8922d5e05f341359f96ce62409194048a70fbbc6934f6a9ec2f046b2",
    "bc4e3755e53c70c1f234b15da678f4058a6c5496d88512737caec293a8547da7",
    "3579ae711aa55342558384edfab6e6517605ac6bf66d04ffcbd8811cc2d3d688",
    "99569b3bb7542f0248a27a5fd2810df417e4e7d01242aa114aee95014c3ea598",
    "82f85023026deeb54466987bf1b8e785b29d095e86036d94c5891d4c8a14fbde",
    "53784645455fe0300fcfc13fb0e371721c2a853684c35813a9182320458dcbf7",
    "6cf8673bb68ef7b58a929f72d3e716e5310ed80040131d212bc565ad3b8e7d8d",
    "65a2e3f38052d4c516cccb4a365f18dd4d1d67fd07007fc7d0916e5c2e37f01d",
    "f39689cdea7b4d526e7a3a61e0b7f4949c4f4b962ae9813887920ed6d756c56e",
    "eca6383c0ae4d325d008cf885ecd91d2c68272cacb857a657dfe6c0bef755e7f",
    "57edccfa3b0c6ebed65e0ad641f44a3f112f07a9c508c71385f980d1fbc36a14",
    "0eb3efacfe04c60ea57d54b1627795da2ab7403bd4a6feb9af8dedd79c808497",
    "e4e936b5a5e8f5d07176c18e14c7638567df0e256c85aa71f82787e49bb62e4a",
    "684ffbb394839d2e82640bcdfba94749b8ef2afa373dc8ea8e2233f470543002",
    "b57b2d13d33b295459f88a6c6465a874cfe5b272cffdf759c57340df3ddc7f8e",
    "3044aabb3323f4fdc13f4bbb9dabbf43c811173a920a9f7161c1af0e101f5c5e",
    "3ecfb527d38dd4f665d3ac60623a41fb1af0442db2afea460a230ab4a9e899ba",
    "66523a8d71a28ccd9b180c9df01ccc9db23519ba5ae85870d8fd9e1df0bbfcce",
    "b6dbd292fd586e96f079e99d9975db76654afcd25a9ddfbf06acf2f7f58a7818",
    "d659fdd0092ba038eaf883af8785189516a8fcc7914f2832f90097b4e909359f",
    "b7a3557c7ea880ef49dd83b391086fa35a3033734bcdba7d294d3d8be6f6a4b4",
    "6e9a6bd8f2b6c8eaf1d582691cbb43769971ab48f71740cb2a3f578adcd0bc2e",
    "4d6465267b2f84a10036dcb2ee3521b992c3983ae1ce76a352ec169b9e5ed1d6",
    "d022d7c2e1e0ca0ee1495860985653aa710c7fee4a45549f22809ed8fd3293b7",
    "08d1c8839b0fe59fdc72012e600221bc4271ec0040230ab12a6ef0b1ace62c49",
    "6e6ec4cdadeadc3105e8a643f23262576db83c8354a07d7fb59b6e295bf80371",
    "1627c9e974176947e14cb2011fae9735b49ccaddbc1aedc0ad96433d02a88074",
    "a90ef9a02a24d6a663a8c2bcf178199747bbb8e90dd86f15d6e87d8e5b984be1",
    "a57260184b6581c99043f450793cea354d1645989d26f81a49947a130527f6b9",
    "a6a9357c73265f9ac671bd154150de913132130d85b8b8097c31f85cf92d2c2e",
    "613411b18dd3ba5f3226f91bebb8dd3cc2a09f7bae42cd5fd6582c8c7e044275",
    "64f8cfab786a33fe777ffd328408afdf0fbe98d5fed40437b36a8798b05674b5",
    "c81b1423a10b144cfd0565a969a8f1df64b13855df4083a3f4f427d138cfcd14",
    "eaab459adb7d0ebc8674d6e36231395b792e194490674fe210395a8554b85b70",
    "88a8dc0a33e5a00fe273790655ee6e40e34e42082d60cf9c8684d8684b73d350",
    "8c4586ef1ebc2bca96433478d89aa87d4a9a1f15e31dab5adc7cd417259ca976",
    "cd9900d832defc7e67f8a14c8662d103aa1fa632933706ae983c34036add2ccd",
    "54fa5c4cb9c6a20f4f72ff6fef1b37f27953c885cac814433092102fdbb45ece",
    "c8cb03b57a057ba1e4bfd088261a1a278f8078caf52f527e211bfd4d684b2045",
    "3266932feefc4668f5fd3d717820002d0663b787936ea6702ec39ccbb1405c07",
    "2a2e4728c2a69ced41f7fae8a1b573f2b794c91ea5c042956a08199ef759807f",
    "a073fc9800ad9a38d78ce9aba1b1725854c580f0ae3ed402883dc7344a922cd5",
    "c4869baf78978fed63297b438e7bcacc1519c2c1a6cab62a4bc68105b98366b2",
    "91724054d1244d999fd522ffdaf512ded8e585e8b17f054c8f920445973d11cc",
    "8ec0f4ef9e025b4283d2def027a1bfadda4358a8951422c909b3c8a892061d77",
    "81e421403a8d72feb0fd58efdb4f9833772cd1dc6202db7397aea17d50cfc04a",
    "f90ce030e57fa461b059928547e4621cb91340f3a640cfd292111dda48597c95",
    "ae6bf360c8a491565a8ab188d2e04ee359297d7c6250617cf6a44162028f2f58",
    "0956b385aba9f071f3db94e9513b6c146a389647fd778819908ab27b9774b508",
    "a5feff8c2afa6d42b81b66de848cc59c1c0e42538e4e094546c31a4f36458174",
    "7df2c599f090ed0d54f4bec7e31f7e28f964688791172b3a2833f73fab7afccf",
    "98660d75e06423f29c354c053742259afb281b97eaa1b93fe11817ab7c883dc5",
    "0e4ef798c5ae258f9673f2ca162dc5b4765a6de23fe5e729444b633323da2a5b",
    "85dce48b717fdeba77db2569e4317ed59bf8338bff6fa68faea322032bac3264",
    "1224989d0c916b1d2aafe1cff80558d58eaa3e64e4c3af358d210c3a5a5f7bbd",
    "1bf060ea0411c51d8d9918091681e81a72ccd02da90dfebbea747cd9fc2ca4b9",
    "47958c28f3e394767c0a99a6b6f67eb2ad8455fe2db4d6609c8dd5bb997c13d9",
    "a8d11044cbfa53c794fa9283b58d0cc613e0d729d0acd60a7413ffc555bb6afd",
    "bf09ee92c4b64e5f94ec58431538341fc34962350c42899789b5144243085c46",
    "df1dcf6f4213e115e8ac1921480d4944de3e7eaa95de6c9a38bb7dda0e119a91",
}

#: Guarded in the tests. Some still appear in code comments.
_IN_TESTS = _EVERYWHERE | {
    "26458a92477569154651e49b1fa8e01e598af21b074dc24ae4540e90c95f2435",
    "beaf8655df6ee40582cc0791ebc3658c23a6bd6858de3565d3cdf3829b4b3df7",
    "4d106fc32f8a46ab31b4fa4772139e72d77df04faf5475a4c264ee42a1457c2c",
    "d31da507cdcac043dffbea52dbd30ba225a427af11fe4ab176ae9939d6fda0c4",
    "1a56e07509932f44a1c8d3776cdaafa8e4ed52488b40f3981a8d583e4f4ef866",
    "4f557362e3f600b0f2e1d806ca465d323dedbf21a248d83849d9706c16b13573",
    "e930aca6a63a5aa84704f3659f17f1ef762a4ea4dcd6fe3fe729f025e7d1e993",
    "22084738e59544c58e2bd3f6587902bddd9331a4b9d156dc679a3556093a04b5",
    "fc27456739ef870b18c5d1e7e3993190db3297cf35d8054ad3dfb7b0feb8af48",
}

#: ADB serials of real phones, guarded everywhere, root files included.
_DEVICE_SERIALS = {
    "3c73122474d68fdd933015f5fd879a8321cb4335e7610194a5ada679332626cd",
    "9e0181b06a4b340ebcf3cf198ced38d8947546b7b3ed30cc9c56e79629bc68b6",
    "7c596951ddcfdb8fa1835c58164d5d2be0e63ef0e5b7f5f17bc93b79f45c9548",
    "75b39b8f68968e7d865b1c6c2eb4d89db89ddf0870fd7a087201842dbe0698f3",
    "99f2e8b062f450378c184982056121694bc75c5dee0486fb32602c242d95e3a0",
    "40fa4a45937a602209ae6c361c0292a8f760a9f12a2243ffc1d64a9721dd5aca",
    "2da4bf6d01c040dfe23dda2c934b9ae9f0c3e9b96e514ba0c32818b9360a9932",
    "9b09c0ce3107c5b02a6c625076958bac3f307422751be40cca2b5882917677e6",
}

_WORD = re.compile(r"[a-z0-9._]+")
# A serial sits inside names such as `config_<serial>.json`: split on anything but letters/digits.
_SERIAL_WORD = re.compile(r"[a-z0-9]+")
_TEXT_SUFFIXES = {".py", ".json", ".yaml", ".yml", ".md", ".txt", ".xml", ".toml", ".cfg", ".ini", ".spec"}
_SKIPPED_DIRS = {"__pycache__", ".pytest_cache", ".git", "build", "dist", "debug_ui"}


def _source_files(root: pathlib.Path):
    if root.is_file():
        yield root
        return
    for path in root.rglob("*"):
        skipped = _SKIPPED_DIRS.intersection(path.relative_to(root).parts)
        if path.suffix in _TEXT_SUFFIXES and not skipped and path.is_file():
            yield path


@functools.lru_cache(maxsize=None)
def _digest(word: str) -> str:
    return hashlib.sha256(word.strip(".").encode()).hexdigest()


def _hits(roots, digests, word=_WORD):
    hits = []
    for root in roots:
        for path in _source_files(root):
            words = set(word.findall(path.read_text(encoding="utf-8", errors="ignore").lower()))
            if any(_digest(word) in digests for word in words):
                hits.append(str(path.relative_to(_CORE)))
    return sorted(hits)


def test_no_guarded_handle_in_the_tests():
    assert _hits([_CORE / "tests"], _IN_TESTS) == []


def test_no_handle_guarded_everywhere_in_the_sources():
    roots = [_CORE / name for name in ("taktik", "bridges", "scripts")]
    assert _hits(roots, _EVERYWHERE) == []


def test_no_real_phone_serial_anywhere():
    roots = [_CORE / name for name in ("taktik", "bridges", "scripts", "tests", ".github")]
    roots += [path for path in _CORE.iterdir() if path.is_file() and path.suffix in _TEXT_SUFFIXES]
    assert _hits(roots, _DEVICE_SERIALS, word=_SERIAL_WORD) == []
