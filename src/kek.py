import os
import sys
import json
import fnmatch
import itertools
from pathlib import Path
from typing import Optional, List, Generator, Tuple, Dict, Union, Set

import requests


# ---------------------------------------------------------------------------
# RDF/Turtle helpers (module-level to keep Kek.to_turtle complexity low)
# ---------------------------------------------------------------------------

def _ttl_uri(squuid: str) -> str:
    return f"kek:{squuid}"


def _ttl_str(value: str) -> str:
    escaped = value.replace("\\", "\\\\").replace('"', '\\"').replace("\n", "\\n")
    return f'"{escaped}"'


def _turtle_media_triples(media: dict) -> List[str]:
    lines: List[str] = []
    uri = _ttl_uri(media["squuid"])
    lines.append(f"{uri}")
    lines.append("    a schema:CreativeWork ;")
    lines.append(f"    schema:name {_ttl_str(media.get('name', ''))} ;")
    media_type = media.get("type", "")
    if media_type:
        lines.append(f"    schema:additionalType {_ttl_str(media_type)} ;")
    state = media.get("state", "")
    if state:
        lines.append(f"    schema:eventStatus {_ttl_str(state)} ;")
    control_date = media.get("controlDate", "")
    if control_date:
        lines.append(f'    kek:controlDate "{control_date}"^^xsd:dateTime ;')
    for op_entry in media.get("operatedBy", []):
        h_squuid = op_entry.get("holder", {}).get("squuid")
        if h_squuid:
            lines.append(f"    schema:publisher {_ttl_uri(h_squuid)} ;")
    lines[-1] = lines[-1].rstrip(" ;") + " ."
    lines.append("")
    return lines


def _turtle_holder_triples(holder: dict) -> List[str]:
    lines: List[str] = []
    uri = _ttl_uri(holder["squuid"])
    lines.append(f"{uri}")
    is_person = holder.get("naturalPerson", False)
    rdf_type = "schema:Person" if is_person else "schema:Organization"
    lines.append(f"    a {rdf_type} ;")
    lines.append(f"    schema:name {_ttl_str(holder.get('name', ''))} ;")
    state = holder.get("state", "")
    if state:
        lines.append(f"    schema:eventStatus {_ttl_str(state)} ;")
    for own_entry in holder.get("owns", []):
        held = own_entry.get("held", {})
        if held.get("squuid"):
            share = own_entry.get("capitalShares", 0)
            lines.append(
                f"    kek:ownsShare [ kek:entity {_ttl_uri(held['squuid'])} ;"
                f' kek:capitalShares "{share}"^^xsd:decimal ] ;'
            )
    for op_entry in holder.get("operates", []):
        held = op_entry.get("held", {})
        if held.get("squuid"):
            lines.append(f"    kek:operates {_ttl_uri(held['squuid'])} ;")
    lines[-1] = lines[-1].rstrip(" ;") + " ."
    lines.append("")
    return lines


class Kek:
    """
    Scraper for media-ownership-data from

    https://kek-online.de
    "Kommission zur Ermittlung der Konzentration im Medienbereich"

    There is an undocumented json API at ``medienvielfaltsmonitor.de/api/v1/``

    First call will bootstrap all data to a cache directory
    and consumes a few minutes..
    """

    DOWNLOAD_DIR: Path = Path(__file__).resolve().parent.parent / "docs" / "data"
    API_URL = "https://medienvielfaltsmonitor.de/api/v1/"

    def __init__(self, caching: Union[bool, str] = True, verbose: bool = False):
        """
        Create an instance to scrape and load the kek data.

        :param caching:
            - `True`: never request a file unless it's missing
            - `False`: request all files!
            - `"upgrade"`: (re-)request media.json and shareholders.json
              and all files that have a changed 'controlDate'

        :param verbose: bool, log stuff to stderr
        """
        assert caching in (True, False, "upgrade")

        self.caching = caching
        self.verbose = verbose
        self._medias = dict()
        self._holders = dict()
        self._session = None
        self._verify_ssl = True

    def get(self, squuid) -> Optional["KekObject"]:
        if squuid in self.medias:
            return self._medias[squuid]
        elif squuid in self.holders:
            return self._holders[squuid]

    def find_media(self, **kwargs) -> Optional["KekObject"]:
        for r in self.filter_media(**kwargs):
            return r

    def find_holder(self, **kwargs) -> Optional["KekObject"]:
        for r in self.filter_holder(**kwargs):
            return r

    def filter_media(self, **kwargs) -> Generator["KekObject", None, None]:
        yield from self._filter(self.medias, filters=kwargs)

    def filter_holder(self, **kwargs) -> Generator["KekObject", None, None]:
        yield from self._filter(self.holders, filters=kwargs)

    def _filter(self, data: dict, filters: dict) -> Generator["KekObject", None, None]:
        for record in data.values():
            matches = True
            for field, value in filters.items():
                # TODO: does only support strings and no dotted paths
                if not fnmatch.fnmatch(record.get(field) or "", value):
                    matches = False
                    break

            if matches:
                yield record

    @property
    def medias(self) -> Dict[str, "KekObject"]:
        if not self._medias:
            self._medias = self._get_object_dict("media/", "media")
        return self._medias

    @property
    def holders(self) -> Dict[str, "KekObject"]:
        if not self._holders:
            self._holders = self._get_object_dict("shareholders/", "shareholders")
        return self._holders

    def _get_object_dict(self, url: str, filename: str) -> Dict[str, "KekObject"]:
        squuid_object_mapping = dict()
        caching = self.caching
        # in "upgrade" mode we load the previous media.json / shareholder.json
        #   and compare each object. If there is any change then download
        #   the single object file again.
        if caching == "upgrade":
            caching = False
            cache_filename = self.DOWNLOAD_DIR / f"{filename}.json"
            if cache_filename.exists():
                previous_object_list = json.loads(cache_filename.read_text())
                squuid_object_mapping = {
                    e["squuid"]: e
                    for e in previous_object_list
                }

        object_list = self._download(url, f"{filename}.json", caching=caching)

        ret_dict = dict()
        for e in object_list:

            caching = self.caching
            if caching == "upgrade":
                caching = True
                if squuid_object_mapping.get(e["squuid"]) != e:
                    caching = False

            data = self._download(
                f"{url}{e['squuid']}",
                f"{filename}/{e['squuid']}.json",
                caching=caching,
            )
            ret_dict[e["squuid"]] = KekObject(self, data)

        return ret_dict

    def _download(
            self,
            url: str,
            filename: str,
            caching: Optional[bool] = None,
    ) -> Union[list, dict]:
        if caching is None:
            caching = self.caching

        cache_filename = self.DOWNLOAD_DIR / filename
        if caching and cache_filename.exists():
            return json.loads(cache_filename.read_text())

        url = f"{self.API_URL}{url}"
        self._log("downloading", url)
        if self._session is None:
            self._session = requests.Session()
            self._session.headers = {
                "User-Agent": "github.com/defgsus/kek-online-archive",
                "Accept": "application/json; encoding=utf-8",
            }

        count = 0
        while True:
            try:
                response = self._session.get(url, verify=self._verify_ssl, timeout=25)
                break
            except requests.exceptions.Timeout:
                self._log(f"TIMEOUT for {url}")
                count += 1
                if count >= 4:
                    raise
            except Exception as e:
                if "certificate" in str(e).lower():
                    self._verify_ssl = False
                else:
                    raise

        self._log("writing", filename)

        path = cache_filename.parent
        os.makedirs(str(path), exist_ok=True)

        data = response.json()

        cache_filename.write_text(
            json.dumps(data, indent=2, ensure_ascii=False)
        )
        return data

    def _log(self, *args, **kwargs):
        if self.verbose:
            kwargs["file"] = sys.stderr
            print(*args, **kwargs)

    def find_indirect_influence(self, squuid: str) -> List[Tuple["KekObject", float]]:
        """
        Find all media outlets (directly or indirectly) influenced by the
        entity identified by *squuid*.  Returns a list of ``(media, weight)``
        tuples where *weight* reflects the cumulative ownership/operation share
        along the chain (1.0 for direct operation, fractional for ownership).

        Addresses the requirement: "Find all media outlets indirectly
        influenced by Person X."
        """
        entity = self.get(squuid)
        if entity is None:
            return []
        return entity.all_owned_medias()

    def find_shared_operators(self) -> Dict[str, List["KekObject"]]:
        """
        Return a mapping of media squuid → list of holder objects that **all**
        operate that same media outlet.  Entries with only a single operator are
        omitted so the result highlights genuine shared-staff / co-operation
        relationships.

        Addresses the requirement: "House A and House B share staff" /
        "Partnerships between organizations."
        """
        media_to_operators: Dict[str, List["KekObject"]] = {}
        for holder in self.holders.values():
            for media in holder.operates:
                if media is None:
                    continue
                msquuid = media["squuid"]
                if msquuid not in media_to_operators:
                    media_to_operators[msquuid] = []
                media_to_operators[msquuid].append(holder)
        return {k: v for k, v in media_to_operators.items() if len(v) > 1}

    def to_turtle(self) -> str:
        """
        Serialize the complete media/shareholder graph as an RDF document in
        Turtle syntax.  The resulting string can be written to a ``.ttl`` file
        and loaded into any triple-store or Linked-Open-Data pipeline.

        Namespace used: ``kek:`` → ``https://kek-online.de/resource/``

        Addresses the interoperability requirement: export to Linked Open Data
        (LOD) / SPARQL-compatible format.
        """
        lines = [
            "@prefix kek: <https://kek-online.de/resource/> .",
            "@prefix schema: <https://schema.org/> .",
            "@prefix xsd: <http://www.w3.org/2001/XMLSchema#> .",
            "",
        ]
        for media in self.medias.values():
            lines.extend(_turtle_media_triples(media))
        for holder in self.holders.values():
            lines.extend(_turtle_holder_triples(holder))
        return "\n".join(lines)

    def to_igraph(self):
        import igraph

        graph = igraph.Graph(directed=True)

        for entry in sorted(
                itertools.chain(self.holders.values(), self.medias.values()),
                key=lambda h: h["name"].lstrip().lower()
        ):
            owned_medias = entry.all_owned_medias()
            all_owners = entry.all_owners()

            graph.add_vertex(
                entry["squuid"],
                type=entry["type"] if entry.is_media() else "shareholder",
                state=entry["state"],
                label=(
                    (entry["name"].strip() or "-")
                    # avoid " in names because visjs can not handle them
                    .replace('"', "'")
                ),
                num_owners=len(all_owners),
                num_owners_weighted=f"{sum(m[1] for m in all_owners):.4f}",
                num_medias=len(owned_medias),
                num_medias_weighted=f"{sum(m[1] for m in owned_medias):.4f}",
            )

        edge_set = set()
        edges = []
        edge_attrs = {"weight": [], "type": []}

        for holder in sorted(self.holders.values(), key=lambda h: h["name"].lstrip().lower()):

            for sub, share in sorted(holder.owns, key=lambda s: s[0]["name"]):
                edge = (holder["squuid"], sub["squuid"])
                if edge not in edge_set:
                    edge_set.add(edge)
                    edges.append(edge)
                    edge_attrs["weight"].append(max(1, share))
                    edge_attrs["type"].append("owns")

            for sub in sorted(holder.operates, key=lambda s: s["name"]):
                edge = (holder["squuid"], sub["squuid"])
                if edge not in edge_set:
                    edge_set.add(edge)
                    edges.append(edge)
                    edge_attrs["weight"].append(100)
                    edge_attrs["type"].append("operates")

        graph.add_edges(edges, edge_attrs)
        return graph


class KekObject(dict):

    def __init__(self, kek: Kek, data: dict):
        # take the "invalid" data on schema errors
        #   e.g. for shareholders/5f02e1b5-ec52-455e-a186-0ad6bd8d6b61
        if not data.get("squuid") and data.get("errors"):
            data = data["value"]

        super().__init__(**data)
        self._kek = kek
        self._hash = int(self["squuid"].replace("-", ""), base=16)

    def __str__(self):
        return json.dumps(self, indent=2)

    def __hash__(self):
        return self._hash

    @property
    def name(self) -> str:
        return self.get("fullName") or self["name"]

    def is_media(self) -> bool:
        return "type" in self

    @property
    def operators(self) -> List["KekObject"]:
        if "operatedBy" not in self:
            return []
        return [
            self._kek.get(o["holder"]["squuid"])
            for o in self["operatedBy"]
        ]

    @property
    def operates(self) -> List["KekObject"]:
        if "operates" not in self:
            return []
        return [
            self._kek.get(o["held"]["squuid"])
            for o in self["operates"]
        ]

    @property
    def owners(self) -> List[Tuple["KekObject", float]]:
        if "ownedBy" not in self:
            return []
        return [
            (self._kek.get(o["holder"]["squuid"]), o.get("capitalShares", 0))
            for o in self["ownedBy"]
        ]

    @property
    def owns(self) -> List[Tuple["KekObject", float]]:
        if "owns" not in self:
            return []
        return [
            (self._kek.get(o["held"]["squuid"]), o.get("capitalShares", 0))
            for o in self["owns"]
        ]

    def all_owned_medias(self) -> List[Tuple["KekObject", float]]:
        if self.is_media():
            return []

        medias = []
        visited = set()
        self._all_owned_medias(medias, visited, 1.)
        return medias

    def _all_owned_medias(
            self,
            medias: List[Tuple["KekObject", float]],
            visited: Set["KekObject"],
            top_share: float,
    ):
        for media in self.operates:
            if media.is_media() and media not in visited:
                medias.append((media, top_share))
                visited.add(media)

        for own, share in self.owns:
            if own not in visited:
                visited.add(own)
                own._all_owned_medias(medias, visited, top_share * share / 100.)

    def all_owners(self) -> List[Tuple["KekObject", float]]:
        visited = set()
        owners = []
        self._all_owners(owners, visited, 1.)
        return owners

    def _all_owners(
            self,
            owners: List[Tuple["KekObject", float]],
            visited: Set["KekObject"],
            top_share: float = 1.,
    ):
        for owner in self.operators:
            if owner not in visited:
                owners.append((owner, top_share))
                visited.add(owner)
                owner._all_owners(owners, visited, top_share)

        for owner, share in self.owners:
            if owner not in visited:
                owners.append((owner, top_share))
                visited.add(owner)
                owner._all_owners(owners, visited, top_share * share / 100.)

    def top_owners(self):
        if self.is_media():
            open_set = {op: 1. for op in self.operators}
        else:
            open_set = {owner: percent for owner, percent in self.owners}

        histogram = dict()
        done_set = set()
        while open_set:
            holder, share = open_set.popitem()
            histogram[holder] = histogram.get(holder, 0) + share

            for owner, percent in holder.owners:
                if (holder, owner) not in done_set:
                    # print(holder.name, ">", owner.name, "|", share, percent / 100)
                    open_set[owner] = open_set.get(owner, 0) + share * percent / 100.

                done_set.add((holder, owner))
        histogram = [
            (owner, histogram[owner] * 100)
            for owner, value in histogram.items()#sorted(histogram, key=lambda h: -histogram[h])
        ]
        histogram.sort(key=lambda h: h[0].name)
        histogram.sort(key=lambda h: -h[1])
        return histogram

    def dump_tree(self, direction: str = "up", prefix: str = "", prefix2: str = "", file=None, _cache=None):
        if _cache is None:
            _cache = set()

        s = self.name
        if self.get("type"):
            s = f"({self['type']}) {s}"
        print(f"{prefix}{prefix2}{s}", file=file)

        prefix = prefix.replace("└", " ").replace("─", " ").replace("├", "│")

        if direction == "up":
            branches = self.operators or self.owners
        elif direction == "down":
            branches = self.operates or self.owns
        else:
            raise ValueError(f"Try direction 'up' or 'down', not '{direction}'")

        if branches and isinstance(branches[0], tuple):
            branches.sort(key=lambda b: -b[1])
        else:
            branches.sort(key=lambda b: b.name)

        if self in _cache:
            if branches:
                print(f"{prefix}└─...")
                return
        _cache.add(self)

        for i, b in enumerate(branches):
            prefix2 = ""
            if isinstance(b, tuple):
                prefix2 = f"{b[1]} "
                b = b[0]

            if i == len(branches) - 1:
                next_prefix = "└─"
            else:
                next_prefix = "├─"
            b.dump_tree(direction=direction, prefix=prefix + next_prefix, prefix2=prefix2, file=file, _cache=_cache)

