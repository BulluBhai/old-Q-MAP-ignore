"""The QLOPB sample files in Tests/fixtures/qlopb_data are SYNTHETIC (09-Nov-26): the committed copies are exactly what
the seeded generator produces, so they can be rebuilt and contain no market data from any source."""

from fixtures import qlopb_synthetic as Q


def test_committed_sample_files_equal_the_generator_output(tmp_path):
    fresh = {p.name: p.read_bytes() for p in Q.write_all(tmp_path)}
    committed = Q.Path(Q.__file__).resolve().parent / "qlopb_data"
    assert sorted(p.name for p in committed.iterdir() if p.is_file()) == sorted(fresh)
    for name, data in fresh.items():
        assert (committed / name).read_bytes() == data, name
