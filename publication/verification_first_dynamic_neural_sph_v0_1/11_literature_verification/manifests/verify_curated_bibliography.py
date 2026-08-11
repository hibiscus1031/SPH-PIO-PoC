#!/usr/bin/env python3
"""Curate, verify, classify, and export the P2 bibliography."""

from __future__ import annotations

import csv
import html
import json
import re
import time
import unicodedata
import urllib.error
import urllib.parse
import urllib.request
from difflib import SequenceMatcher
from pathlib import Path

P2 = Path(__file__).resolve().parents[1]
RAW_CSV = P2 / "raw_candidates/raw_candidate_bibliography.csv"
SEARCH_DATE = "2026-08-05"

# Crossref occasionally omits chapter-level contributors.  These narrow
# overrides are accepted only after checking the official publisher page.
AUTHOR_OVERRIDES_BY_DOI = {
    "10.1017/cbo9780511802270.009": "Eugenia Kalnay",
}

SELECTED_RAW_IDS = """
RAW004 RAW010 RAW014 RAW016 RAW017 RAW022 RAW023 RAW031 RAW043 RAW044 RAW056 RAW066 RAW077 RAW080
RAW101 RAW104 RAW114 RAW125 RAW128 RAW129 RAW142 RAW145 RAW149 RAW168 RAW169 RAW173 RAW174 RAW178
RAW181 RAW188 RAW193 RAW197 RAW201 RAW210 RAW214 RAW216 RAW218 RAW225 RAW252 RAW260 RAW265 RAW268
RAW271 RAW273 RAW285 RAW289 RAW293 RAW294 RAW298 RAW304 RAW310 RAW314 RAW319 RAW320 RAW326 RAW335
RAW340 RAW346 RAW347 RAW367 RAW380 RAW397 RAW399 RAW400 RAW404 RAW406 RAW409 RAW418 RAW424 RAW428
RAW429 RAW443 RAW454
""".split()

CORE_RAW = set("""
RAW004 RAW014 RAW016 RAW017 RAW022 RAW023 RAW031 RAW044 RAW056 RAW066 RAW077 RAW114 RAW142 RAW149
RAW168 RAW178 RAW188 RAW193 RAW210 RAW218 RAW289 RAW294 RAW320 RAW335 RAW346
""".split())

MANUAL = [
    {
        "manual_id": "M001", "themes": "T1;T2", "level": "CORE-A_DIRECT_COMPETITOR",
        "title": "Neural SPH: Improved Neural Modeling of Lagrangian Fluid Dynamics",
        "authors": "Artur Toshev; Jonas A. Erbesdobler; Nikolaus A. Adams; Johannes Brandstetter",
        "year": "2024", "venue": "Proceedings of the 41st International Conference on Machine Learning",
        "volume": "235", "issue": "", "pages_or_article": "48428–48452", "doi": "",
        "publisher": "PMLR", "publisher_url": "https://proceedings.mlr.press/v235/toshev24a.html",
        "secondary_url": "https://arxiv.org/abs/2402.06275", "publication_status": "published conference paper",
        "preprint_relation": "arXiv:2402.06275 is the preprint; PMLR is the formal version",
        "evidence_access": "FULL_TEXT", "notes": "Official PMLR page and paper PDF checked.",
    },
    {
        "manual_id": "M002", "themes": "T1;T4;T5", "level": "CORE-A_DIRECT_COMPETITOR",
        "title": "JAX-SPH: A Differentiable Smoothed Particle Hydrodynamics Framework",
        "authors": "Artur P. Toshev; Harish Ramachandran; Jonas A. Erbesdobler; Gianluca Galletti; Johannes Brandstetter; Nikolaus A. Adams",
        "year": "2024", "venue": "ICLR 2024 Workshop on AI4DifferentialEquations in Science",
        "volume": "", "issue": "", "pages_or_article": "", "doi": "",
        "publisher": "OpenReview", "publisher_url": "https://openreview.net/forum?id=8X5PXVmsHW",
        "secondary_url": "https://arxiv.org/abs/2403.04750", "publication_status": "accepted workshop paper",
        "preprint_relation": "arXiv:2403.04750 corresponds to the OpenReview workshop paper",
        "evidence_access": "FULL_TEXT", "notes": "Official OpenReview PDF and arXiv record checked.",
    },
    {
        "manual_id": "M003", "themes": "T1;T3;T4", "level": "CORE-A_DIRECT_COMPETITOR",
        "title": "Physics-informed machine learning with smoothed particle hydrodynamics: Hierarchy of reduced Lagrangian models of turbulence",
        "authors": "Michael Woodward; Yifeng Tian; Criston Hyett; Chris Fryer; Mikhail Stepanov; Daniel Livescu; Michael Chertkov",
        "year": "2023", "venue": "Physical Review Fluids", "volume": "8", "issue": "5",
        "pages_or_article": "054602", "doi": "10.1103/physrevfluids.8.054602", "publisher": "American Physical Society",
        "publisher_url": "https://journals.aps.org/prfluids/abstract/10.1103/PhysRevFluids.8.054602",
        "secondary_url": "https://doi.org/10.1103/PhysRevFluids.8.054602", "publication_status": "published journal article",
        "preprint_relation": "formal version retained", "evidence_access": "FULL_TEXT", "notes": "Publisher abstract and accepted manuscript available.",
    },
    {
        "manual_id": "M004", "themes": "T1;T2", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "LagrangeBench: A Lagrangian Fluid Mechanics Benchmarking Suite",
        "authors": "Artur P. Toshev; Gianluca Galletti; Fabian Fritz; Stefan Adami; Nikolaus A. Adams",
        "year": "2024", "venue": "Advances in Neural Information Processing Systems", "volume": "36", "issue": "",
        "pages_or_article": "", "doi": "10.52202/075280-2830", "publisher": "NeurIPS",
        "publisher_url": "https://papers.neurips.cc/paper_files/paper/2023/hash/ccac3b120c7dc86d45f56830732b62be-Abstract-Datasets_and_Benchmarks.html",
        "secondary_url": "https://arxiv.org/abs/2309.16342", "publication_status": "published conference paper",
        "preprint_relation": "arXiv:2309.16342 is the preprint", "evidence_access": "FULL_TEXT", "notes": "Official NeurIPS paper checked.",
    },
    {
        "manual_id": "M005", "themes": "T2", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Learning to Simulate Complex Physics with Graph Networks",
        "authors": "Alvaro Sanchez-Gonzalez; Jonathan Godwin; Tobias Pfaff; Rex Ying; Jure Leskovec; Peter Battaglia",
        "year": "2020", "venue": "Proceedings of the 37th International Conference on Machine Learning", "volume": "119", "issue": "",
        "pages_or_article": "8459–8468", "doi": "", "publisher": "PMLR",
        "publisher_url": "https://proceedings.mlr.press/v119/sanchez-gonzalez20a.html", "secondary_url": "https://arxiv.org/abs/2002.09405",
        "publication_status": "published conference paper", "preprint_relation": "arXiv:2002.09405 is the preprint",
        "evidence_access": "FULL_TEXT", "notes": "Official PMLR paper checked.",
    },
    {
        "manual_id": "M006", "themes": "T2", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Lagrangian Fluid Simulation with Continuous Convolutions",
        "authors": "Benjamin Ummenhofer; Lukas Prantl; Nils Thuerey; Vladlen Koltun",
        "year": "2020", "venue": "International Conference on Learning Representations", "volume": "", "issue": "",
        "pages_or_article": "", "doi": "", "publisher": "OpenReview",
        "publisher_url": "https://openreview.net/forum?id=B1lDoJSYDH", "secondary_url": "https://arxiv.org/abs/1910.14324",
        "publication_status": "published conference paper", "preprint_relation": "arXiv:1910.14324 is the preprint",
        "evidence_access": "FULL_TEXT", "notes": "Official OpenReview paper checked.",
    },
    {
        "manual_id": "M007", "themes": "T2", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Learning Particle Dynamics for Manipulating Rigid Bodies, Deformable Objects, and Fluids",
        "authors": "Yunzhu Li; Jiajun Wu; Russ Tedrake; Joshua B. Tenenbaum; Antonio Torralba",
        "year": "2019", "venue": "International Conference on Learning Representations", "volume": "", "issue": "",
        "pages_or_article": "", "doi": "", "publisher": "OpenReview",
        "publisher_url": "https://openreview.net/forum?id=rJgbSn09Ym", "secondary_url": "https://arxiv.org/abs/1810.01566",
        "publication_status": "published conference paper", "preprint_relation": "arXiv:1810.01566 is the preprint",
        "evidence_access": "FULL_TEXT", "notes": "Official conference/preprint identity checked.",
    },
    {
        "manual_id": "M008", "themes": "T2;T5", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Learning Mesh-Based Simulation with Graph Networks",
        "authors": "Tobias Pfaff; Meire Fortunato; Alvaro Sanchez-Gonzalez; Peter W. Battaglia",
        "year": "2021", "venue": "International Conference on Learning Representations", "volume": "", "issue": "",
        "pages_or_article": "", "doi": "", "publisher": "OpenReview",
        "publisher_url": "https://openreview.net/forum?id=roNqYL0_XP", "secondary_url": "https://arxiv.org/abs/2010.03409",
        "publication_status": "published conference paper", "preprint_relation": "arXiv:2010.03409 is the preprint",
        "evidence_access": "FULL_TEXT", "notes": "Official conference/preprint identity checked.",
    },
    {
        "manual_id": "M009", "themes": "T4", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Solver-in-the-Loop: Learning from Differentiable Physics to Interact with Iterative PDE-Solvers",
        "authors": "Kiwon Um; Robert Brand; Yun Fei; Philipp Holl; Nils Thuerey",
        "year": "2020", "venue": "Advances in Neural Information Processing Systems", "volume": "33", "issue": "",
        "pages_or_article": "6111–6122", "doi": "", "publisher": "NeurIPS",
        "publisher_url": "https://proceedings.neurips.cc/paper/2020/hash/43e4e6a6f341e00671e123714de019a8-Abstract.html",
        "secondary_url": "https://arxiv.org/abs/2007.00016", "publication_status": "published conference paper",
        "preprint_relation": "arXiv:2007.00016 is the preprint", "evidence_access": "FULL_TEXT", "notes": "Official NeurIPS paper checked.",
    },
    {
        "manual_id": "M010", "themes": "T4", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Scalable Differentiable Physics for Learning and Control",
        "authors": "Yi-Ling Qiao; Junbang Liang; Vladlen Koltun; Ming C. Lin",
        "year": "2020", "venue": "Proceedings of the 37th International Conference on Machine Learning", "volume": "119", "issue": "",
        "pages_or_article": "7847–7856", "doi": "", "publisher": "PMLR",
        "publisher_url": "https://proceedings.mlr.press/v119/qiao20a.html", "secondary_url": "https://arxiv.org/abs/2002.11250",
        "publication_status": "published conference paper", "preprint_relation": "arXiv:2002.11250 is the preprint",
        "evidence_access": "FULL_TEXT", "notes": "Official PMLR paper checked.",
    },
    {
        "manual_id": "M011", "themes": "T3", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Hamiltonian Neural Networks", "authors": "Sam Greydanus; Misko Dzamba; Jason Yosinski",
        "year": "2019", "venue": "Advances in Neural Information Processing Systems", "volume": "32", "issue": "",
        "pages_or_article": "", "doi": "", "publisher": "NeurIPS",
        "publisher_url": "https://proceedings.neurips.cc/paper/2019/hash/26cd8ecadce0d4efd6cc8a8725cbd1f8-Abstract.html",
        "secondary_url": "https://arxiv.org/abs/1906.01563", "publication_status": "published conference paper",
        "preprint_relation": "arXiv:1906.01563 is the preprint", "evidence_access": "FULL_TEXT", "notes": "Official NeurIPS paper checked.",
    },
    {
        "manual_id": "M012", "themes": "T3", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "Lagrangian Neural Networks", "authors": "Miles Cranmer; Sam Greydanus; Stephan Hoyer; Peter Battaglia; David Spergel; Shirley Ho",
        "year": "2020", "venue": "ICLR 2020 Workshop on Integration of Deep Neural Models and Differential Equations", "volume": "", "issue": "",
        "pages_or_article": "", "doi": "", "publisher": "OpenReview",
        "publisher_url": "https://openreview.net/forum?id=iE8tFa4Nq", "secondary_url": "https://arxiv.org/abs/2003.04630",
        "publication_status": "accepted workshop paper", "preprint_relation": "arXiv:2003.04630 corresponds to workshop paper",
        "evidence_access": "FULL_TEXT", "notes": "Official OpenReview/preprint identity checked.",
    },
    {
        "manual_id": "M013", "themes": "T3", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "E(n) Equivariant Graph Neural Networks", "authors": "Victor Garcia Satorras; Emiel Hoogeboom; Max Welling",
        "year": "2021", "venue": "Proceedings of the 38th International Conference on Machine Learning", "volume": "139", "issue": "",
        "pages_or_article": "9323–9332", "doi": "", "publisher": "PMLR",
        "publisher_url": "https://proceedings.mlr.press/v139/satorras21a.html", "secondary_url": "https://arxiv.org/abs/2102.09844",
        "publication_status": "published conference paper", "preprint_relation": "arXiv:2102.09844 is the preprint",
        "evidence_access": "FULL_TEXT", "notes": "Official PMLR paper checked.",
    },
    {
        "manual_id": "M014", "themes": "T3", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "SE(3)-Equivariant and Steerable Graph Networks", "authors": "Johannes Brandstetter; Rob Hesselink; Elise van der Pol; Erik J. Bekkers; Max Welling",
        "year": "2022", "venue": "International Conference on Learning Representations", "volume": "", "issue": "",
        "pages_or_article": "", "doi": "", "publisher": "OpenReview",
        "publisher_url": "https://openreview.net/forum?id=_xwr8gOBeV1", "secondary_url": "https://arxiv.org/abs/2110.02905",
        "publication_status": "published conference paper", "preprint_relation": "arXiv:2110.02905 is the preprint",
        "evidence_access": "FULL_TEXT", "notes": "Official OpenReview/preprint identity checked.",
    },
    {
        "manual_id": "M015", "themes": "T6", "level": "CORE-B_METHOD_COMPARATOR",
        "title": "REFORMS: Consensus-based Recommendations for Machine-learning-based Science",
        "authors": "Sayash Kapoor; Emily M. Cantrell; Kenny Peng; Thanh Hien Pham; Christopher A. Bail; Odd Erik Gundersen; Jake M. Hofman; Jessica Hullman; Michael A. Lones; Momin M. Malik; Priyanka Nanayakkara; Russell A. Poldrack; Inioluwa Deborah Raji; Michael Roberts; Matthew J. Salganik; Marta Serra-Garcia; Brandon M. Stewart; Gilles Vandewiele; Arvind Narayanan",
        "year": "2024", "venue": "Science Advances", "volume": "10", "issue": "18", "pages_or_article": "eadk3452",
        "doi": "10.1126/sciadv.adk3452", "publisher": "AAAS", "publisher_url": "https://www.science.org/doi/10.1126/sciadv.adk3452",
        "secondary_url": "https://pmc.ncbi.nlm.nih.gov/articles/PMC11092361/", "publication_status": "published journal article",
        "preprint_relation": "formal version retained", "evidence_access": "FULL_TEXT", "notes": "Publisher and PMC full text checked.",
    },
    {
        "manual_id": "M016", "themes": "T1", "level": "CORE-C_CONTEXT",
        "title": "An Intelligent SPH Framework Based on Machine-Learned Residual Correction for Elliptic PDEs",
        "authors": "Ammar Qarariyah; Tianhui Yang; Fang Deng", "year": "2025", "venue": "Algorithms", "volume": "18", "issue": "12",
        "pages_or_article": "803", "doi": "10.3390/a18120803", "publisher": "MDPI",
        "publisher_url": "https://www.mdpi.com/1999-4893/18/12/803", "secondary_url": "https://doaj.org/article/c6e2b8ba1d004f6f8a833b588f2d78a1",
        "publication_status": "published journal article", "preprint_relation": "formal version retained", "evidence_access": "FULL_TEXT",
        "notes": "Static elliptic residual correction; not a dynamic neural-SPH precedent.",
    },
    {
        "manual_id": "M017", "themes": "T1", "level": "CORE-C_CONTEXT",
        "title": "Data-driven kernel selection in Smoothed Particle Hydrodynamics using machine learning: automated hyperparameter optimization for heat conduction problems",
        "authors": "Lilian Dobrowolski de Carvalho Augusto; Eduardo Tadeu Bacalhau; Helio Pedro Amaral Souto", "year": "2026",
        "venue": "Engineering with Computers", "volume": "42", "issue": "", "pages_or_article": "115",
        "doi": "10.1007/s00366-026-02354-w", "publisher": "Springer Nature",
        "publisher_url": "https://link.springer.com/article/10.1007/s00366-026-02354-w", "secondary_url": "https://doi.org/10.1007/s00366-026-02354-w",
        "publication_status": "published journal article", "preprint_relation": "formal version retained; withdrawn Elsevier duplicate excluded",
        "evidence_access": "FULL_TEXT", "notes": "Hyperparameter selection, not dynamic learned correction.",
    },
    {
        "manual_id": "M018", "themes": "T2", "level": "CORE-C_CONTEXT",
        "title": "FluidMLP: A general method for learning Lagrangian fluid simulation", "authors": "Yongzhi Li; et al.", "year": "2022",
        "venue": "Simulation Modelling Practice and Theory", "volume": "116", "issue": "", "pages_or_article": "102623",
        "doi": "10.1016/j.simpat.2022.102623", "publisher": "Elsevier", "publisher_url": "https://www.sciencedirect.com/science/article/pii/S1569190X22001010",
        "secondary_url": "https://doi.org/10.1016/j.simpat.2022.102623", "publication_status": "published journal article",
        "preprint_relation": "formal version retained", "evidence_access": "ABSTRACT_ONLY", "notes": "Fully learned Lagrangian simulator context.",
    },
    {
        "manual_id": "M019", "themes": "T4;T5", "level": "CORE-C_CONTEXT",
        "title": "DiffTaichi: Differentiable Programming for Physical Simulation", "authors": "Yuanming Hu; Tzu-Mao Li; Luke Anderson; Jonathan Ragan-Kelley; Frédo Durand", "year": "2020",
        "venue": "ACM Transactions on Graphics", "volume": "39", "issue": "6", "pages_or_article": "1–20",
        "doi": "", "publisher": "OpenReview", "publisher_url": "https://openreview.net/forum?id=B1eB5xSFvr",
        "secondary_url": "https://arxiv.org/abs/1910.00935", "publication_status": "published journal article",
        "preprint_relation": "arXiv:1910.00935 is the preprint", "evidence_access": "FULL_TEXT", "notes": "General differentiable simulation comparator.",
    },
    {
        "manual_id": "M020", "themes": "T4;T5", "level": "CORE-C_CONTEXT",
        "title": "ChainQueen: A Real-Time Differentiable Physical Simulator for Soft Robotics", "authors": "Yuanming Hu; Jiancheng Liu; Andrew Spielberg; Joshua B. Tenenbaum; William T. Freeman; Jiajun Wu; Daniela Rus; Wojciech Matusik",
        "year": "2019", "venue": "2019 International Conference on Robotics and Automation", "volume": "", "issue": "", "pages_or_article": "6265–6271",
        "doi": "10.1109/icra.2019.8794333", "publisher": "IEEE", "publisher_url": "https://ieeexplore.ieee.org/document/8794333",
        "secondary_url": "https://arxiv.org/abs/1810.01054", "publication_status": "published conference paper",
        "preprint_relation": "arXiv:1810.01054 is the preprint", "evidence_access": "FULL_TEXT", "notes": "MPM-based differentiable simulator comparator.",
    },
    {
        "manual_id": "M021", "themes": "T2;T4;T5", "level": "CORE-C_CONTEXT",
        "title": "SPNets: Differentiable Fluid Dynamics for Deep Neural Networks", "authors": "Connor Schenck; Dieter Fox",
        "year": "2018", "venue": "Proceedings of The 2nd Conference on Robot Learning", "volume": "87", "issue": "", "pages_or_article": "317–335",
        "doi": "", "publisher": "PMLR", "publisher_url": "https://proceedings.mlr.press/v87/schenck18a.html",
        "secondary_url": "https://arxiv.org/abs/1806.06094", "publication_status": "published conference paper",
        "preprint_relation": "arXiv:1806.06094 is the preprint", "evidence_access": "FULL_TEXT", "notes": "Differentiable particle/PBF method, not SPH correction.",
    },
]


def norm(s: str) -> str:
    s = html.unescape(s or "")
    s = unicodedata.normalize("NFKD", s).encode("ascii", "ignore").decode("ascii").lower()
    return re.sub(r"[^a-z0-9]+", " ", s).strip()


def crossref_exact(doi: str) -> tuple[dict | None, str]:
    if not doi:
        return None, "NO_DOI_REGISTERED"
    url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    for attempt in range(5):
        try:
            request = urllib.request.Request(url, headers={"User-Agent": "SPH-PIO-PoC-P2/1.0"})
            with urllib.request.urlopen(request, timeout=45) as response:
                return json.load(response)["message"], "CROSSREF_MATCH"
        except urllib.error.HTTPError as exc:
            status_code = exc.code
            if status_code == 404:
                return None, "CROSSREF_NOT_FOUND"
        except Exception:
            status_code = "ERROR"
        time.sleep(1.5 * (attempt + 1))
    return None, f"CROSSREF_HTTP_{status_code}"


def resolve_doi(doi: str) -> tuple[int | str, str]:
    if not doi:
        return "NOT_APPLICABLE", ""
    class NoRedirect(urllib.request.HTTPRedirectHandler):
        def redirect_request(self, req, fp, code, msg, headers, newurl):
            return None
    try:
        request = urllib.request.Request(
            "https://doi.org/" + doi,
            headers={"User-Agent": "Mozilla/5.0 (SPH-PIO literature verification)"},
            method="GET",
        )
        opener = urllib.request.build_opener(NoRedirect)
        try:
            response = opener.open(request, timeout=45)
            return response.status, response.headers.get("Location", "") or response.geturl()
        except urllib.error.HTTPError as exc:
            if 300 <= exc.code < 400:
                return exc.code, exc.headers.get("Location", "")
            return exc.code, ""
    except Exception as exc:
        return "ERROR", f"{type(exc).__name__}: {exc}"


def cr_authors(item: dict) -> str:
    out = []
    for a in item.get("author", []):
        name = " ".join(x for x in [a.get("given", ""), a.get("family", "")] if x).strip()
        if name:
            out.append(name)
    return "; ".join(out)


def cr_year(item: dict) -> str:
    for k in ("published-print", "published-online", "published", "issued"):
        p = item.get(k, {}).get("date-parts", [])
        if p and p[0]:
            return str(p[0][0])
    return ""


def classify_raw(row: dict) -> str:
    if row["candidate_id"] in CORE_RAW:
        if row["candidate_id"] == "RAW077":
            return "CORE-A_DIRECT_COMPETITOR"
        return "CORE-B_METHOD_COMPARATOR" if any(t in row["themes"] for t in ("T2", "T3", "T4", "T5", "T6")) else "CORE-C_CONTEXT"
    return "CORE-C_CONTEXT"


def verify_record(base: dict, source_kind: str) -> dict:
    doi = (base.get("doi") or "").lower()
    cr, cr_status = crossref_exact(doi)
    resolver_status, resolver_location = resolve_doi(doi)
    title = base.get("title", "")
    title_similarity = ""
    field_conflicts = []
    if cr:
        cr_title = " ".join(cr.get("title") or [])
        title_similarity = round(SequenceMatcher(None, norm(title), norm(cr_title)).ratio(), 4)
        if title_similarity < 0.82:
            field_conflicts.append("title")
        title = cr_title or title
        authors = AUTHOR_OVERRIDES_BY_DOI.get(doi) or cr_authors(cr) or base.get("authors", "")
        year = cr_year(cr) or base.get("year", "")
        venue = " ".join(cr.get("container-title") or []) or base.get("venue", "")
        volume = cr.get("volume", "") or base.get("volume", "")
        issue = cr.get("issue", "") or base.get("issue", "")
        pages = cr.get("page") or cr.get("article-number") or base.get("pages_or_article", "")
        publisher = cr.get("publisher", "") or base.get("publisher", "")
        cr_url = "https://api.crossref.org/works/" + urllib.parse.quote(doi, safe="")
    else:
        authors, year, venue = base.get("authors", ""), base.get("year", ""), base.get("venue", "")
        volume, issue, pages = base.get("volume", ""), base.get("issue", ""), base.get("pages_or_article", "")
        publisher, cr_url = base.get("publisher", ""), ""
    if doi and (not cr or not resolver_location):
        field_conflicts.append("doi_resolution")
    if not doi and not (base.get("publisher_url") and base.get("secondary_url")):
        field_conflicts.append("dual_source")
    required_metadata = {
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "publisher": publisher,
        "publisher_url": base.get("publisher_url") or resolver_location or (cr or {}).get("URL", ""),
    }
    unverified_reasons = [f"missing_{name}" for name, value in required_metadata.items() if not str(value).strip()]
    if field_conflicts:
        status = "BIBLIOGRAPHIC_CONFLICT"
    elif unverified_reasons:
        status = "UNVERIFIED_REJECTED"
    else:
        status = "VERIFIED_NO_DOI_REGISTERED" if not doi else "VERIFIED"
    return {
        "citation_id": "",
        "source_record_id": base.get("candidate_id") or base.get("manual_id"),
        "themes": base.get("themes", ""),
        "literature_level": base.get("level") or classify_raw(base),
        "core_reference": (base.get("candidate_id") in CORE_RAW) or (base.get("manual_id") in {f"M{i:03d}" for i in range(1, 16)}),
        "title": title,
        "authors": authors,
        "year": year,
        "venue": venue,
        "volume": volume,
        "issue": issue,
        "pages_or_article": pages,
        "doi": doi,
        "publication_status": base.get("publication_status", "published/registered work"),
        "publisher": publisher,
        "publisher_url": base.get("publisher_url") or resolver_location or (cr or {}).get("URL", ""),
        "crossref_url": cr_url,
        "secondary_url": base.get("secondary_url") or ("https://doi.org/" + doi if doi else ""),
        "preprint_relation": base.get("preprint_relation", "formal DOI record retained; duplicate versions not separately retained"),
        "evidence_access": base.get("evidence_access", "ABSTRACT_ONLY" if cr and cr.get("abstract") else "METADATA_ONLY"),
        "metadata_verification_source_1": "Crossref exact DOI" if doi else "official publisher/conference page",
        "metadata_verification_source_2": "DOI resolver" if doi else "preprint/secondary official record",
        "crossref_status": cr_status,
        "doi_resolver_http_status": resolver_status,
        "doi_resolver_location": resolver_location,
        "title_similarity_to_discovery": title_similarity,
        "field_conflicts": ";".join(field_conflicts),
        "unverified_reasons": ";".join(unverified_reasons),
        "status": status,
        "notes": base.get("notes", ""),
        "search_cutoff_date": SEARCH_DATE,
        "source_kind": source_kind,
    }


def reject_reason(row: dict) -> str:
    t = norm(row.get("title", ""))
    if "correction to" in t or "corrigendum" in t or "review for" in t or "decision letter" in t:
        return "duplicate/correction/peer-review record"
    if row.get("crossref_type") not in {"journal-article", "proceedings-article", "book-chapter", "posted-content", "report"}:
        return "secondary source only"
    if not any(k in t for k in ("particle", "fluid", "sph", "differenti", "adjoint", "momentum", "hamilton", "lagrang", "verification", "validation", "manufactured", "equivariant", "solver", "graph")):
        return "no relevant methodological evidence"
    if any(k in t for k in ("medical", "financial", "web credibility", "cyber", "sequence alignment", "antenna cavity", "balitsky", "chromatographic")):
        return "not relevant physical-solver domain"
    return "screened out after thematic relevance review"


def main() -> None:
    raw = list(csv.DictReader(RAW_CSV.open(encoding="utf-8-sig")))
    raw_by_id = {r["candidate_id"]: r for r in raw}
    missing = sorted(set(SELECTED_RAW_IDS) - set(raw_by_id))
    if missing:
        raise SystemExit(f"Missing selected raw IDs: {missing}")
    verified = []
    for rid in SELECTED_RAW_IDS:
        verified.append(verify_record(raw_by_id[rid], "Crossref-discovered"))
        time.sleep(0.2)
    for row in MANUAL:
        verified.append(verify_record(row, "manual-seed-from-official-literature-search"))
        time.sleep(0.2)
    verified.sort(key=lambda r: (r["literature_level"], r["year"], r["title"].casefold()))
    for idx, row in enumerate(verified, 1):
        row["citation_id"] = f"V{idx:03d}"

    ok = [r for r in verified if r["status"].startswith("VERIFIED")]
    conflicts = [r for r in verified if r["status"] == "BIBLIOGRAPHIC_CONFLICT"]
    unverified = [r for r in verified if r["status"] == "UNVERIFIED_REJECTED"]
    rejects = []
    for row in raw:
        if row["candidate_id"] in SELECTED_RAW_IDS:
            continue
        rejects.append({
            "candidate_id": row["candidate_id"], "title": row["title"], "doi": row["doi"],
            "themes": row["themes"], "status": "EXCLUDED", "rejection_reason": reject_reason(row),
        })
    for row in conflicts:
        rejects.append({
            "candidate_id": row["source_record_id"], "title": row["title"], "doi": row["doi"],
            "themes": row["themes"], "status": "BIBLIOGRAPHIC_CONFLICT", "rejection_reason": row["field_conflicts"],
        })
    for row in unverified:
        rejects.append({
            "candidate_id": row["source_record_id"], "title": row["title"], "doi": row["doi"],
            "themes": row["themes"], "status": "UNVERIFIED_REJECTED", "rejection_reason": row["unverified_reasons"],
        })

    out_dir = P2 / "verified_records"
    out_dir.mkdir(parents=True, exist_ok=True)
    fields = list(ok[0].keys())
    with (out_dir / "verified_bibliography.csv").open("w", newline="", encoding="utf-8-sig") as h:
        w = csv.DictWriter(h, fieldnames=fields); w.writeheader(); w.writerows(ok)
    (out_dir / "verified_bibliography.json").write_text(json.dumps(ok, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    rej_dir = P2 / "rejected_records"; rej_dir.mkdir(parents=True, exist_ok=True)
    with (rej_dir / "rejected_bibliography.csv").open("w", newline="", encoding="utf-8-sig") as h:
        w = csv.DictWriter(h, fieldnames=list(rejects[0].keys())); w.writeheader(); w.writerows(rejects)
    summary = {
        "raw_candidates": len(raw), "curated_for_verification": len(verified), "verified": len(ok),
        "bibliographic_conflicts": len(conflicts), "unverified_rejected": len(unverified), "excluded": len(rejects),
        "core": sum(bool(r["core_reference"]) for r in ok),
        "levels": {level: sum(r["literature_level"] == level for r in ok) for level in sorted({r["literature_level"] for r in ok})},
        "no_doi_registered": sum(r["status"] == "VERIFIED_NO_DOI_REGISTERED" for r in ok),
    }
    print(json.dumps(summary, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
