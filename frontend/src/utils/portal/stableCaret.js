// Vue patches text nodes after each input; retain the user's selection across that patch.
const selections = new WeakMap()
function textOffset(element, node, offset) {
  const range = element.ownerDocument.createRange()
  range.selectNodeContents(element)
  range.setEnd(node, offset)
  return range.toString().length
}
function textPosition(element, offset) {
  const walker = element.ownerDocument.createTreeWalker(element, 4)
  let node, last
  while ((node = walker.nextNode())) {
    last = node
    if (offset <= node.length) return [node, offset]
    offset -= node.length
  }
  return last ? [last, last.length] : [element, 0]
}
export const vStableCaret = {
  beforeUpdate(element) {
    const selection = element.ownerDocument.getSelection()
    if (!element.isContentEditable || !selection?.rangeCount
      || !element.contains(selection.anchorNode) || !element.contains(selection.focusNode)) return
    selections.set(element, [textOffset(element, selection.anchorNode, selection.anchorOffset), textOffset(element, selection.focusNode, selection.focusOffset)])
  },
  updated(element) {
    const offsets = selections.get(element)
    selections.delete(element)
    if (!offsets || !element.isContentEditable || element.ownerDocument.activeElement !== element) return
    element.ownerDocument.getSelection()?.setBaseAndExtent(...textPosition(element, offsets[0]), ...textPosition(element, offsets[1]))
  }
}
