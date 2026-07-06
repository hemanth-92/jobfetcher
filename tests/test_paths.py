from jobfetcher.paths import OutputPaths, ensure_output_dir, ensure_parent_dir


def test_output_paths_for_directory():
    paths = OutputPaths.for_directory("results")
    assert str(paths.jobs_csv) == "results/jobs.csv"
    assert str(paths.links_csv) == "results/jobs_links.csv"
    assert str(paths.links_html) == "results/jobs.html"
    assert str(paths.market_txt) == "results/market_summary.txt"
    assert str(paths.seen_jobs) == "results/seen_jobs.json"


def test_ensure_output_dir_creates_results_folder(tmp_path):
    output_dir = tmp_path / "results"
    ensure_output_dir(output_dir)
    assert output_dir.exists()


def test_ensure_parent_dir_creates_nested_directories(tmp_path):
    output_path = tmp_path / "results" / "mid.csv"
    ensure_parent_dir(output_path)
    assert output_path.parent.exists()