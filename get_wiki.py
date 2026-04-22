import urllib.request, re
req = urllib.request.Request('https://pt.wikipedia.org/wiki/Servi%C3%A7o_Nacional_de_Aprendizagem_Industrial', headers={'User-Agent': 'Mozilla/5.0'})
html = urllib.request.urlopen(req).read().decode('utf-8')
imgs = re.findall(r'src="([^"]+)"', html)
print([img for img in imgs if 'senai' in img.lower() or 'logo' in img.lower()])