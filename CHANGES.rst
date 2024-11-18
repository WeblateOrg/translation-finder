Changelog
=========

2.19
----

* Released on 18th November 2024.
* Fixed crasn on corrupt YAML files.

2.18
----

* Released on 13th November 2024.
* Fixed crash on corrupted Transifex configuration.
* Improved app store metadata detection.
* Improved template detection for text files.
* Improved detection of iOS translation files.
* Added type annotations.

2.17
----

* Released on 7th November 2024.
* Added support for Format.JS files.
* Offer bilingual configuration for CSV.

2.16
----

* Released on 20th December 2023.
* Fixed detection UTF-16 Strings files.
* Fixed detection of files with some special chars.
* Added support for Mobile Kotlin resources.

2.15
----

* Released on 13th January 2023.
* Added support for gotext JSON.
* Added support for i18next JSON v4.
* REUSE 3.0 compliance.

2.14
----

* Released on 11th August 2022.
* Added detection of XLIFF format variants.
* Added support for TXT format.
* Added support for adding hint via API.

2.13
----

* Released on 17th May 2022.
* Dropped support for Python 3.6.
* Improved detection of PWG 5100.13 based strings files.
* Added support for ResourceDictionary format.

2.12
----

* Released on 25th February 2022.
* Use charset-normalizer for charset detection.
* Improved performance when scanning huge directories.

2.11
----

* Released on 17th January 2022.
* Exclude common virtualenv directories.
* Tested against Python 3.10.

2.10
----

* Released on 9th August 2021.
* Fixed detection of POT files in top level directory.
* Added support for detecting stringsdict files.

2.9
---

* Released on 29th January 2021.
* Fixed discovery execution in standalone environments.

2.8
---

* Released on 29th January 2021.
* Added detection of RC files.
* Added detection of TBX files.

2.7
---

* Released on 4th January 2021.
* Fixed support for CSV files.
* Added eager detection mode.
* Added type hints.

2.6
---

* Released on 26th November 2020.
* Added support for CSV files.
* Improved detection of PHP files.
* Removed filtering of test files.
* Finder now skips non accessible directories.

2.5
---

* Released on 4th November 2020.
* Improved POT detection in some cases.
* Tested with Python 3.9.

2.4
---

* Released on 19th October 2020.
* Fixed build of wheel packages.

2.3
---

* Released on 19th October 2020.
* New dependency on weblate-language-data module.
* Reduced amount of false positives on language codes inside a filename.
* Improved iOS strings encoding detection.
* Removed charamel dependency.

2.2
---

* Released on 15th September 2020.
* Added detection of Golang i18n json files.
* Added detection of TOML files.
* Improved charset detection by switching to charamel.
* Dropped support for Python 3.5.
* Added detection of ARB files.

2.1
---

* Released on 27th May 2020.
* Added discovery support for formats newly supported by Weblate (HTML,
  IDML, OpenDocument, InnoSetup and INI).

2.0
---

* Released on 14th April 2020.
* Dropped support for Python 2.
* Improved i18next detection.
* Improved detection of monolingual templates.

1.8
---

* Released on 5th March 2020.
* Fixed discovery of filenames with digits.
* Fixed crash on invalid YAML files.

1.7
---

* Released on 15th October 2019.
* Improved handling of invalid JSON files.
* Improved detection of flat JSON files.
* Improved compatibility with OSX.
* Improved detection of new base with gettext PO files.

1.6
---

* Released on 26th June 2019.
* Improved discovery of POT files.
* Added support for subtitle files supported in Weblate 3.7.
* Improved detection of actual JSON formats.
* Added support for detecting PHP files.
* Improved detection of YAML formats.

1.5
---

* Released on 29th May 2019.
* Various performance improvements.
* Added detection of Fluent translations.
* Improved detection of language code within filename.
* Added detection of YAML translations.

1.4
---

* Released on 29th April 2019.
* Improved detection in Perl code.
* Extended skip list for language codes.

1.3
---

* Released on 28th April 2019.
* Improved detection of nested language codes with country suffix.
* Improved processing of Transifex .tx/config files.
* Include discovery metadata in API results.
* Improve detection of files in source directory.

1.2
---

* Released on 17th April 2019.
* Fixed discovery of monolingual files in root.
* Improved detection of non language paths.

1.1
---

* Released on 20th March 2019.
* Improved detection of translation with full language code.
* Improved detection of language code in directory and file name.
* Improved detection of language code separated by full stop.
* Added detection for app store metadata files.
* Added detection for JSON files.
* Ignore symlinks during discovery.
* Improved detection of matching pot files in several corner cases.
* Improved detection of monolingual Gettext.

1.0
---

* Released on 22nd January 2019.
* Discover Joomla INI files.

0.3
---

* Released on 6th December 2018.
* Code restructuring.
* Better handling of multiple language codes in path.
* Extended test cases.

0.2
---

* Released on 30th November 2018.
* Added detection for monolingual Gettext, XLIFF and web extension.
* Detect new base for Gettext and Qt TS.
* Detect encoding of properties files.
* Automatically import Transifex configuration.

0.1
---

* Released on 19th October 2018.
* Initial release.
