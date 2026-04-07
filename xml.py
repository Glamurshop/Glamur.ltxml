import requests
import re
from time import sleep

# =========================
# CONFIG
# =========================

SHOPIFY_DOMAIN = "xxcw0w-1f.myshopify.com"
ACCESS_TOKEN = "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"

GRAPHQL_URL = f"https://{SHOPIFY_DOMAIN}/admin/api/2023-10/graphql.json"

HEADERS = {
    "Content-Type": "application/json",
    "X-Shopify-Access-Token": ACCESS_TOKEN
}

OUTPUT_FILE = "glamur_lt.xml"

# TEST MODE
TEST_MODE = True
TEST_LIMIT = 50

# =========================
# FETCH PRODUCTS (LT)
# =========================

def fetch_products(country_code="LT", locale="lt"):

    variants = []
    cursor = None

    total_api = 0

    while True:

        query = f"""
        {{
          productVariants(first: 100{', after: "' + cursor + '"' if cursor else ''}) {{
            pageInfo {{ hasNextPage }}
            edges {{
              cursor
              node {{
                id
                sku
                barcode
                inventoryQuantity
                image {{ src }}
                selectedOptions {{ name value }}
                product {{
                  id
                  handle
                  vendor
                  status
                  productType
                  featuredImage {{ src }}
                  title
                  bodyHtml
                  translations(locale: "{locale}") {{
                    key
                    value
                  }}
                }}
                contextualPricing(context: {{country: {country_code}}}) {{
                  price {{ amount }}
                }}
              }}
            }}
          }}
        }}
        """

        response = requests.post(GRAPHQL_URL, headers=HEADERS, json={"query": query})
        data = response.json()

        edges = data["data"]["productVariants"]["edges"]

        for edge in edges:

            node = edge["node"]
            product = node["product"]

            total_api += 1

            if product["status"] != "ACTIVE":
                continue

            # =====================
            # PRICE
            # =====================
            price = float(node.get("contextualPricing", {}).get("price", {}).get("amount") or 0)
            if price <= 0:
                continue

            # =====================
            # STOCK
            # =====================
            inventory = node.get("inventoryQuantity") or 0
            if inventory <= 0:
                continue

            # =====================
            # TRANSLATIONS (LT)
            # =====================
            translations = product.get("translations", [])

            title_lt = next((t["value"] for t in translations if t["key"] == "title"), None)
            body_lt = next((t["value"] for t in translations if t["key"] == "body_html"), None)

            title = title_lt or product.get("title")
            description = re.sub(r"<.*?>", "", body_lt or product.get("bodyHtml") or "").strip()

            # variant title
            variant_name = " ".join([opt["value"] for opt in (node.get("selectedOptions") or [])])
            full_title = f"{title} {variant_name}".strip()

            # =====================
            # IMAGE
            # =====================
            image = ""
            
            if node.get("image") and node["image"].get("src"):
                image = node["image"]["src"]
            
            elif product.get("featuredImage") and product["featuredImage"].get("src"):
                image = product["featuredImage"]["src"]

            # =====================
            # APPEND
            # =====================
            variants.append({
                "id": node["id"].split("/")[-1],
                "title": full_title,
                "handle": product["handle"],
                "vendor": product["vendor"],
                "sku": node["sku"] or "",
                "barcode": node["barcode"] or "",
                "price": f"{price:.2f}",
                "inventory": inventory,
                "image": image,
                "description": description,
                "productType": product["productType"] or product["vendor"]
            })

            # TEST LIMIT
            if TEST_MODE and len(variants) >= TEST_LIMIT:
                print(f"TEST MODE STOP: {TEST_LIMIT} products")
                return variants

        print(f"Fetched: {len(variants)}")

        if not data["data"]["productVariants"]["pageInfo"]["hasNextPage"]:
            break

        cursor = edges[-1]["cursor"]
        sleep(0.5)

    return variants


# =========================
# HELPERS
# =========================

def slugify(text):
    text = (text or "").lower()
    text = re.sub(r"[^a-z0-9]+", "-", text)
    return text.strip("-")


# =========================
# XML BUILD (FULL STRUCTURE)
# =========================

def build_xml(products):

    with open(OUTPUT_FILE, "w", encoding="utf-8") as f:

        f.write('<?xml version="1.0" encoding="utf-8"?>\n')
        f.write("<products>\n")

        for p in products:

            f.write(f'  <product id="{p["id"]}">\n')

            f.write(f'    <title><![CDATA[{p["title"]}]]></title>\n')
            f.write(f'    <price>{p["price"]}</price>\n')
            f.write(f'    <condition>new</condition>\n')
            f.write(f'    <stock>{p["inventory"]}</stock>\n')

            f.write(f'    <ean_code><![CDATA[{p["barcode"]}]]></ean_code>\n')

            f.write("    <additional_eans></additional_eans>\n")

            f.write(f'    <manufacturer_code><![CDATA[{p["sku"]}]]></manufacturer_code>\n')
            f.write(f'    <manufacturer><![CDATA[{p["vendor"]}]]></manufacturer>\n')
            f.write(f'    <model><![CDATA[{p["sku"]}]]></model>\n')

            f.write(f'    <image_url><![CDATA[{p["image"]}]]></image_url>\n')

            f.write("    <additional_images></additional_images>\n")

            f.write(f'    <product_url><![CDATA[https://glamur.lt/products/{p["handle"]}?variant={p["id"]}]]></product_url>\n')

            f.write(f'    <category_id>0</category_id>\n')
            f.write(f'    <category_name><![CDATA[{p["productType"]}]]></category_name>\n')
            f.write(f'    <category_link><![CDATA[https://glamur.lt/collections/{slugify(p["vendor"])}]]></category_link>\n')

            f.write(f'    <description><![CDATA[{p["description"]}]]></description>\n')

            # DELIVERY (pagal tavo setup)

            f.write("    <delivery>\n")
            
            f.write("      <home_delivery>\n")
            f.write("        <working_days><![CDATA[4-5]]></working_days>\n")
            f.write("        <price><![CDATA[2.99]]></price>\n")
            f.write("      </home_delivery>\n")
            
            f.write("      <parcel_locker_delivery>\n")
            f.write("        <working_days><![CDATA[4-5]]></working_days>\n")
            f.write("        <price><![CDATA[2.99]]></price>\n")
            f.write("      </parcel_locker_delivery>\n")
            
            f.write("    </delivery>\n")

            f.write("  </product>\n")

        f.write("</products>\n")

    print(f"\nXML CREATED: {len(products)} products")


# =========================
# MAIN
# =========================

if __name__ == "__main__":

    print("Fetching LT products...\n")

    products = fetch_products()

    print("\nBuilding XML...\n")

    build_xml(products)

    print("\nDONE")
