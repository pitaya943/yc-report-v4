"""How fonts/NotoSansTC-Regular.ttf was made. Not part of the normal run.

    pip install fonttools==4.68.0
    curl -L -o NotoSansTC-wght.ttf \
      'https://raw.githubusercontent.com/google/fonts/main/ofl/notosanstc/NotoSansTC%5Bwght%5D.ttf'
    python build_font.py NotoSansTC-wght.ttf NotoSansTC-Regular.ttf

The upstream file is a variable font whose default weight is Thin (100).
reportlab cannot select a weight axis, so the Regular (400) instance is cut
out once and committed. Licence: SIL Open Font License 1.1, see OFL.txt.
"""
import sys

from fontTools.ttLib import TTFont
from fontTools.varLib import instancer

source, target = sys.argv[1:3]
font = instancer.instantiateVariableFont(TTFont(source), {"wght": 400}, updateFontNames=True)
font.save(target)
