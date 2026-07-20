"""Unit test: verify parser correctly maps real JustDial __NEXT_DATA__ rows."""
import json
import sys
import os

# Allow importing from src/
sys.path.insert(0, os.path.join(os.path.dirname(__file__), ".."))

from src.parser import rows_to_dicts, parse_listing, parse_page

# Real columnar data captured from JustDial (3 rows)
FIXTURE = json.loads(r"""
{"columns":["docid","name","distance","NewAddress","lat","lon","paidStatus","compRating","verified","rateThis","mappointer","opstring","area","opennow","type","VNumber","totalReviews","video","city","thumbnail","totJdReviews","favflag","attr_data","an","shopfront","ishotel","vertical","vertical_name","discount_Offer","vertical_data","position_flag","Jadoopic","sharedt_url","cancall","wpnumber","action_node","idxno","linefive","newadd","newaddcolor","dimages","viewchange","photocnt","pdg","nameln","NewAddressln","address_flg","ask_mobile","hcatarr","callalocation","compRatingln","catalog_flag","jdpay","ratecard","ds","inapp","bd_params","jtkr","useshare","weburl","rev","nwtaglin","tag","starhotel","revarr","offertag","ratingtag","resp_rate","pincode","guarantee","event_data","msg_pop","scd","loccity","docatt","catarray","arealn","service_catalog","is_lawyer","price_tagline","rateColor","seo_info","logo","ad_listing","card_info","dimages_tag","apiprm","extra_field"],"data":[["011PXX11.XX11.170123181948.M3H8","Pind Balluchi Restaurant","","Sector 63 Market Noida Sector 62","28.627413","77.375454","6","4.1","1",1,"1",{"status":"<span>Opens at </span><span>11:30 AM</span>","timing":"11:30 am - 11:00 pm"},"Block H-1 A Noida Sector 62",0,"Restaurants, North Indian Restaurants","08123061405","4,642 Ratings","1","Delhi","https://thumb.jpg","4,642",0,{"node1":"","node2":"<span>2600 Price for two</span>","node3":["<span>9 Years in Business</span>",1,0],"node1color":[]},{},0,0,[],"restaurant","",[],1,"https://checkin.jpg","https://www.justdial.com/DT-23YAEUU2UEY",1,[],""  ,1,"","","",[]  ,[0,2,0],"33","P","Pind Balluchi Restaurant","Sector 63 Market Noida Sector 62",1,0,{"id":10339065,"nid":10339065,"name":"North Indian Restaurants","lin":""},"encoded==","4.1",0,{"img":"","redirection_url":""},{},"0",1,{"did":"011PXX11.XX11.170123181948.M3H8","cmp_params":{"bcity":"Noida","barea":"Noida Sector 62","bpncdbd":"201309","paidstatus":"6","misc":"131072","ask_mobile":0},"bilang":""},"encoded2==",0,"Noida/Pind-Balluchi-Restaurant-Sector-63-Market-Noida-Sector-62/011PXX11-XX11-170123181948-M3H8_BZDET","",["Candle Light Dinner"],[{"tag_name":"Trending","bg_colour":"#5271dd","txt_colour":"#FFFFFF","tag_image":"trending.svg"}],"",[]  ,{},[]  ,{"lead":"48","lead_resp":"0","avg_resp_time_sec":""},"201309","",{"cname":"Pind Balluchi Restaurant","docid":"011PXX11.XX11.170123181948.M3H8","rating":"4.1","rating_cnt":"4642","city":"Noida","dcity":"Delhi","area":"Noida Sector 62","pin":"201309","ds":"0","pdg":"P","paid":"6","jd_verified":"1","guarantee":"","trust":"0","verified":"1","pos":1,"tag":"Trending"},1,"23YAEUU2UEY","Noida",[{"h":"1","d":"<span>Opens at 11:30 AM</span>"},{"h":1,"d":"<span>2600</span>"}],[],  "Noida Sector 62",[],0,[],  "#007A0C",[],  "https://logo.jpg",0,[],["1ce0ewg"],"",[]],["011PXX11.XX11.220331165453.V4D8","Mr. Sardar Ji Restaurant and Caterers","","Nearby Clock Tower Hari Nagar","28.6258441","77.1153032","5","3.6","1",1,"1",{"status":"<span>Opens at </span><span>09:00 AM</span>","timing":"9:00 am - 11:59 pm"},"Near Baba Garment Hari Nagar",0,"Restaurants","08511068303","272 Ratings","","delhi","https://thumb2.jpg","272",0,{"node1":"","node2":"","node3":["<span>20 Years in Business</span>",0,0],"node1color":[]},{},0,0,[],"restaurant","",[],0,"https://checkin2.jpg","https://www.justdial.com/DT-23BKDMJT85C",1,[],""  ,2,"","","",[]  ,[0,2,0],"4","","Mr. Sardar Ji Restaurant and Caterers","Nearby Clock Tower Hari Nagar",1,0,{"id":10408936,"nid":10408936,"name":"Restaurants","lin":""},"encoded3==","3.6",0,{"img":"","redirection_url":""},{},"0",1,{"did":"011PXX11.XX11.220331165453.V4D8","cmp_params":{"bcity":"Delhi","barea":"Hari Nagar","bpncdbd":"110064","paidstatus":"5","misc":"8589942784","ask_mobile":0},"bilang":""},"encoded4==",0,"Delhi/Mr-Sardar-Ji-Restaurant-and-Caterers-Nearby-Clock-Tower-Hari-Nagar/011PXX11-XX11-220331165453-V4D8_BZDET","",["Chinese","North Indian","Available for Functions"],[{"tag_name":"Quick Response","bg_colour":"#5271dd","txt_colour":"#FFFFFF","tag_image":"responsive.svg"}],"",[]  ,{},[]  ,{"lead":"99","lead_resp":"2","avg_resp_time_sec":""},"110064","",{"cname":"Mr. Sardar Ji Restaurant and Caterers","docid":"011PXX11.XX11.220331165453.V4D8","rating":"3.6","rating_cnt":"272","city":"Delhi","dcity":"delhi","area":"Hari Nagar","pin":"110064","verified":"0","pos":2},1,"23BKDMJT85C","Delhi",[],[],"Hari Nagar",[],0,[],"#108723",[],"",0,[],["vaknePB56j"],"",[]],["011PXX11.XX11.190217125514.L2W7","New Champaran Meat House","","Near Mcd Tol Tax New Ashok Nagar","28.5895267","77.3086753","5","3.9","1",1,"1",{"status":"<span>Opens at </span><span>12:00 PM</span>","timing":"12:00 pm - 11:30 pm"},"New Ashok Nagar Rd New Ashok Nagar",0,"Restaurants, North Indian Restaurants","08511222687","791 Ratings","","delhi","https://thumb3.jpg","791",0,{"node1":"","node2":"<span>550 Price for two</span>","node3":["",0,0],"node1color":[]},{},0,0,[],"restaurant","",[],0,"https://checkin3.jpg","https://www.justdial.com/DT-23EY22YQ2QQ",1,[],""  ,3,"","","",[]  ,[0,2,0],"11","","New Champaran Meat House","Near Mcd Tol Tax New Ashok Nagar",1,0,{"id":10339065,"nid":10339065,"name":"North Indian Restaurants","lin":""},"encoded5==","3.9",0,{"img":"","redirection_url":""},{},"0",1,{"did":"011PXX11.XX11.190217125514.L2W7","cmp_params":{"bcity":"Delhi","barea":"New Ashok Nagar","bpncdbd":"110096","paidstatus":"5","misc":"8589934592","ask_mobile":0},"bilang":""},"encoded6==",0,"Delhi/New-Champaran-Meat-House-Near-Mcd-Tol-Tax-New-Ashok-Nagar/011PXX11-XX11-190217125514-L2W7_BZDET","",["Delivery","Dine-in","Mughlai"],[{"tag_name":"Quick Response","bg_colour":"#5271dd","txt_colour":"#FFFFFF","tag_image":"responsive.svg"}],"",[]  ,{},[]  ,{"lead":"71","lead_resp":"4","avg_resp_time_sec":""},"110096","",{"cname":"New Champaran Meat House","docid":"011PXX11.XX11.190217125514.L2W7","rating":"3.9","rating_cnt":"791","city":"Delhi","dcity":"delhi","area":"New Ashok Nagar","pin":"110096","verified":"0","pos":3},1,"23EY22YQ2QQ","Delhi",[],[],"New Ashok Nagar",[],0,[],"#108723",[],"",0,[],["j4v15ma4re"],"",[]]]  }
""")


def test_row_parsing():
    rows = rows_to_dicts(FIXTURE)
    assert len(rows) == 3

    results = [parse_listing(r, "Delhi") for r in rows]
    results = [r for r in results if r]
    assert len(results) == 3

    # --- Row 0: Pind Balluchi ---
    r0 = results[0]
    assert r0["businessName"] == "Pind Balluchi Restaurant"
    assert r0["category"] == "Restaurants"
    assert r0["phone"] == "08123061405"
    assert "Sector 63" in r0["address"]
    assert r0["locality"] == "Noida Sector 62"
    assert r0["city"] == "Noida"          # loccity wins over input city
    assert r0["rating"] == 4.1
    assert r0["reviewCount"] == 4642
    assert r0["isVerified"] is True
    assert r0["hasWebsite"] is False
    assert r0["websiteUrl"] is None
    assert "Pind-Balluchi" in r0["profileUrl"]
    assert r0["openNow"] is False          # opennow = 0
    assert r0["yearsInBusiness"] == 9

    # --- Row 1: Mr. Sardar Ji ---
    r1 = results[1]
    assert r1["businessName"] == "Mr. Sardar Ji Restaurant and Caterers"
    assert r1["category"] == "Restaurants"
    assert r1["phone"] == "08511068303"
    assert r1["city"] == "Delhi"
    assert r1["rating"] == 3.6
    assert r1["reviewCount"] == 272
    assert r1["isVerified"] is True        # verified field = "1"
    assert r1["yearsInBusiness"] == 20

    # --- Row 2: New Champaran ---
    r2 = results[2]
    assert r2["businessName"] == "New Champaran Meat House"
    assert r2["rating"] == 3.9
    assert r2["reviewCount"] == 791
    assert r2["yearsInBusiness"] is None   # node3[0] is "" — no years

    print("All assertions passed!")
    for i, r in enumerate(results):
        print(f"\n--- Listing {i+1} ---")
        for k, v in r.items():
            print(f"  {k}: {v!r}")


if __name__ == "__main__":
    test_row_parsing()
