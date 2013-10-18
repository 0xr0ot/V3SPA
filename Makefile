
# OS X Sublime Text 2 hack
PATH := $(PATH):/usr/local/bin

COFFEE = PATH=$(PATH) coffee
LESS = PATH=$(PATH) lessc

VESPA_JS_OUT = static/js/vespa.js
VESPA_JS_SRC = src/vespa.litcoffee  \
               src/models.litcoffee \
               src/router.litcoffee \
               src/editor.litcoffee

VESPA_CSS_OUT = static/css/vespa.css
VESPA_CSS_SRC = src/vespa.less       \
                src/editor.less      \
                src/less/common.less \
                src/less/define.less

all: $(VESPA_JS_OUT) $(VESPA_CSS_OUT)
	@make -C external/avispa
	@cp -f external/avispa/out/avispa.js static/js/
	@cp -f external/avispa/out/avispa.css static/css/

$(VESPA_JS_OUT): $(VESPA_JS_SRC)
	$(COFFEE) -j $(VESPA_JS_OUT) -c $(VESPA_JS_SRC)

$(VESPA_CSS_OUT): $(VESPA_CSS_SRC)
	$(LESS) -x --no-color --include-path=src/less $< $@

clean:
	@find . -type f -name \*.pyc -exec rm -f {} +
	@make -C external/avispa clean

distclean: clean
	@rm -f $(VESPA_JS_OUT) $(VESPA_CSS_OUT)
