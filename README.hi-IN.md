# Bunch of AIgents (BoA)

यह README इन भाषाओं में भी उपलब्ध है:\
[de-DE](README.de-DE.md), [en-GB](README.en-GB.md), [en-US](README.md), [es-AR](README.es-AR.md), [es-ES](README.es-ES.md), [fr-FR](README.fr-FR.md), [he-IL](README.he-IL.md), [it-IT](README.it-IT.md), [ja-JP](README.ja-JP.md), [ko-KR](README.ko-KR.md), [pt-BR](README.pt-BR.md), [pt-PT](README.pt-PT.md), [ru-RU](README.ru-RU.md), [zh-CN](README.zh-CN.md)

## यह क्या है

सेल्फ़-होस्टेड AI एजेंट, जो GNU/Linux सर्वर (Debian या Alpine) पर अलग-अलग उपयोगकर्ताओं के रूप में चलते हैं।

हर एजेंट के पास अपना:

- होम डायरेक्टरी
- crontab
- शेल एक्सेस
- Samba शेयर
- RAG (ज़रूरत हो तो)
- आदि

आप उन तक सीधे वेब ऐप से या Telegram या Discord के ज़रिए पहुँच सकते हैं।

## स्क्रीनशॉट

![Bunch of AIgents का इंटरफ़ेस](https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/doc/screenshot.png)

## इंस्टॉल करना

इसे `root` के रूप में चलाएँ।

**Debian** (PID 1 के रूप में systemd के साथ):

```bash
curl -fsSL https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-debian.sh \
  | bash -s -- --install --email you@example.com
```

**Alpine Linux**:

```bash
wget -qO- https://raw.githubusercontent.com/nipegun/bunch-of-aigents/main/deploy/install-update-reinstall-alpine.sh \
  | sh -s -- --install --email you@example.com
```

> **Alpine पर Playwright नहीं है।** Playwright musl के लिए कोई build प्रकाशित नहीं
> करता, इसलिए Alpine पर एजेंटों के पास ब्राउज़र नहीं होता: जब कोई एजेंट `browser.*`
> टूलों में से किसी को बुलाता है, तो वे यही बताते हैं। बाक़ी सब कुछ Debian की तरह
> ही काम करता है।

## दस्तावेज़ पढ़ें

आगे पढ़ें:

- [doc/MANUAL.hi-IN.md](doc/MANUAL.hi-IN.md) — इसे इंस्टॉल करना, सेट अप करना और इस्तेमाल करना सीखने के लिए।
- [doc/CODE.hi-IN.md](doc/CODE.hi-IN.md) — यह समझने के लिए कि यह कैसे बना है (डेवलपरों और AI मॉडलों के लिए)।

## इस प्रोजेक्ट को प्रायोजित करें

- **मुझे काम पर रखें।** लोग और कंपनियाँ नई सुविधाएँ जोड़ने के लिए मुझे काम पर रख सकते हैं: [मुझे ईमेल करें](mailto:nipegun@gmail.com?subject=About%20the%20BoA%20repo)।
- **मुझे एक कॉफ़ी पिलाएँ:** [buymeacoffee.com/nipegun](https://buymeacoffee.com/nipegun)।
- **GitHub Sponsors.** आप GitHub पर भी इस प्रोजेक्ट को आर्थिक सहयोग दे सकते हैं: [github.com/sponsors/nipegun](https://github.com/sponsors/nipegun)।
