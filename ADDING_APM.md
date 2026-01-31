https://github.com/opensearch-project/dashboards-observability/blob/main/Using-Docker.md

[] Upgrade opensearch, osd, data-prepper to staging 3.5.0 images  
[] Create prometheus datasource for metrics and confirm it works. 
* clone repo
* build 
* 


```bash
curl 'http://localhost:5601/api/directquery/dataconnections' \
  -X POST \
  -H 'User-Agent: Mozilla/5.0 (Macintosh; Intel Mac OS X 10.15; rv:145.0) Gecko/20100101 Firefox/145.0' \
  -H 'Accept: */*' \
  -H 'Accept-Language: en-US,en;q=0.5' \
  -H 'Accept-Encoding: gzip, deflate, br, zstd' \
  -H 'Referer: http://localhost:5601/app/dataSources/configure/Prometheus' \
  -H 'Content-Type: application/json' \
  -H 'osd-version: 3.5.0' \
  -H 'osd-xsrf: osd-fetch' \
  -H 'Origin: http://localhost:5601' \
  -H 'Connection: keep-alive' \
  -H 'Cookie: _ga_BQV14XK08F=GS2.1.s1766188011$o45$g1$t1766190023$j60$l0$h519364192; _ga=GA1.1.1109299810.1763664614; token=eyJhbGciOiJIUzI1NiIsInR5cCI6IkpXVCJ9.eyJpZCI6Ijk3MDg5MGJiLWVhNjItNDhjNS04ODMwLTEyNWRjMDMwODdmOCIsImV4cCI6MTc3MDg0NjY2OCwianRpIjoiM2Q3OWQ2YmItMGMyYS00MTQyLTkwYjUtMTMzMGI2MDdjYTMwIn0.11X4G114JO3lHrxXDWoSAmfaGaBimfBljLrE457RloI; security_authentication=Fe26.2**d6548e3835a88dba8162dde6d97f60153f8ce4ddcc4b968740c87521bb418279*_09xg7-j3U6ZKPQlRE85Sw*zusmwPhS9XyHMfkqGeEvtOoDCCKQIm25eUjzSrWIquW7riKXYH-mfQ_NSdcrGC22oV-JkPU9RGVz4MOglzAEM1IAgu1mb6p_xPOsLBxCMPzrC9FEvp8FWdvkScE2h5MuhxJpPAD_SSeaGEsXoc09aF05-AGtGxWASykmnr3E1tipjcrXREFy6vrbVZUrP7daqhaVIqCQd0ahry8vjvnlxPYHNi0g4RhyyD3p6xfwokY**d9e277b43f230f8d93e9ff9856dd7cb0c83151bcd94a7d04b16047fe9ea03ad8*W8dZxTqNb9I-2RCm8ELrMnrIdQjiPQazUncib7Nd8v4' \
  -H 'Sec-Fetch-Dest: empty' \
  -H 'Sec-Fetch-Mode: cors' \
  -H 'Sec-Fetch-Site: same-origin' \
  -H 'Priority: u=0' \
  -H 'Pragma: no-cache' \
  -H 'Cache-Control: no-cache' \
  --data-raw '{"name":"test-prometheus","allowedRoles":[],"connector":"prometheus","properties":{"prometheus.uri":"http://prometheus:9090"}}'
```