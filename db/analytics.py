import db.entries
import db.occurrences

def onTabulateRelations():
    # TODO: or do we search through occurrences?
    occs = db.occurrences.allOccurrences()

    relations = {}
    for occ in occs:
        nearby = occ.getNearby(2) # change to actual value later
        if nearby:
            #TODO: unicode error trying to print lists containing unicode
            # string reprs with non-ascii characters
            tmin = str(min(nearby))
            print(nearby, end=' ')
            print("::", end=' ')
            print(tmin)
        else:
            print("no tmin")

def letterDistribution():
    """
    Calculate the distribution of first letters in index entries. This
    uses the sort keys, since the presumed purpose is to get an idea of
    how much space should be allowed for each letter in a paper index
    (averaged over the whole database).

    The report includes four columns:
        Letter - self-explanatory.
        Freq(uency) - how many times that letter appears as the first of
            an entry's sort key.
        Percent - the frequency divided by the total number of index
            entries, expressed as a percentage.
        Resid(ual) - the mean frequency minus this letter's frequency. A
            positive value indicates this letter is more common than
            average; a negative that it is less common than average.
    """
    entries = db.entries.allEntries()
    totalEntries = len(entries)

    # Find the first character of every sort key and tally them up.
    firstChars = {}
    for entry in entries:
        char = entry.sortKey[:1].lower()
        firstChars[char] = firstChars.get(char, 0) + 1

    # Combine digits and symbols into single entries.
    cleanedChars = {}
    for char in firstChars:
        if char.isalpha():
            cleanedChars[char] = firstChars[char]
        elif char.isdigit():
            cleanedChars['num'] = cleanedChars.get('num', 0) + \
                                  firstChars[char]
        else: # symbol
            cleanedChars['sym'] = cleanedChars.get('sym', 0) + \
                                  firstChars[char]

    # Get a list indicating the order to sort our dictionary elements in
    # for display, placing 'num' and 'sym' at top in that order.
    sortOrder = sorted(list(cleanedChars.keys()), key=lambda i:
            i if i not in ('num', 'sym')
            else ('01' if i == 'num' else '02'))

    # Find the longest count so we know how to justify that column.
    maxLen = 0
    for letter in sortOrder:
        thisLen = len(str(cleanedChars[letter]))
        if thisLen > maxLen:
            maxLen = thisLen

    # Calculate summary statistics and print them out.
    avgfreq = float(totalEntries) / len(sortOrder)
    avgperc = 100 * float(avgfreq) / totalEntries
    report = ["<html>"
              "There are %i entries in your database.<br>" % totalEntries,
              "The average frequency is %.02f (%.02f%%)." % (avgfreq,
                                                             avgperc)]
    # Set up headers.
    report.append('''<br><table><thead><tr>
                         <th>Letter&nbsp;</th>
                         <th align=right>Freq&nbsp;</th>
                         <th align=right>Percent&nbsp;</th>
                         <th align=right>Resid&nbsp;</th>
                     </tr></thead>''')

    # Create a table row for each letter.
    for letter in sortOrder:
        if letter not in ('num', 'sym'):
            printLetter = letter.upper()
        else:
            printLetter = 'Digit' if letter == 'num' else 'Symbol'

        count = cleanedChars[letter]
        percentage = 100 * float(cleanedChars[letter]) / totalEntries
        resid = percentage - avgperc
        color = "color:red;" if resid < 0 else ""
        report.append("<tr><td>%s</td>"
                      "<td align=right>%i&nbsp;</td>"
                      "<td align=right>%.02f%%&nbsp;</td>"
                      '<td align=right style="%s">%.02f%%&nbsp;</td>'
                      % (printLetter, count, percentage, color, resid))
    report.append("</table></html>")
    return '\n'.join(report)
