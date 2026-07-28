import os, requests

def main():
    gms = os.environ["DATAHUB_GMS_URL"]
    headers = {"Authorization": f"Bearer {os.environ.get('DATAHUB_GMS_TOKEN','')}"}
    from demo.seed import URNS
    for urn in URNS.values():
        r = requests.get(f"{gms}/entities/{requests.utils.quote(urn, safe='')}",
                         headers=headers, timeout=10)
        assert r.status_code == 200, f"{urn}: {r.status_code}"
    print("seed verified: 4/4 entities resolvable")

if __name__ == "__main__":
    main()
